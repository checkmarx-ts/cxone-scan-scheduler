#!/usr/bin/python3
import logging, argparse, utils, asyncio
from __agent__ import __scanagent__
from cxone_api import CxOneClient
from cxone_api.high.scans import ScanInvoker, ScanInspector, ScanLoader
from cxone_api.high.projects import ProjectRepoConfig
from cxone_api.low.projects import retrieve_last_scan
from cxone_api.low.scans import retrieve_list_of_scans, retrieve_scan_workflow
from cxone_api.util import json_on_ok
from requests import Response
from posix_ipc import Semaphore, BusyError, O_CREAT
from utils import (create_engine_scan_config, 
                   get_threads_config, 
                   get_api_timeout_config, 
                   get_api_retry_delay_config, 
                   get_api_retries_config,
                   get_fetch_timeout_config,
                   get_fetch_throttle)
from time import perf_counter_ns
from datetime import datetime
from uuid import uuid4
from typing import List, Union

__CHECK_DELAY_S = 30
__SCHEDULE_TAG = "scheduled"

utils.configure_normal_logging()
__log = logging.getLogger("scan executor")


parser = argparse.ArgumentParser(description="A program to execute scans in CheckmarxOne as a Scheduler cron job.")

parser.add_argument('--projectid', '-p', action='store', type=str, required=True, dest="projectid", help="The CxOne project id found in the tenant.")
parser.add_argument('--engine', '-e', action='append', type=str, required=True, dest="engines", help="The engines to use for the scan.")
parser.add_argument('--repo', '-r', action='store', type=str, required=True, dest="repo", help="The code repository URL.")
parser.add_argument('--branch', '-b', action='store', type=str, required=True, dest="branch", help="The code repository branch.")
parser.add_argument('--schedule', '-s', action='store', type=str, required=False, default='unknown', dest="schedule", help="The schedule string assigned to the 'scheduled' scan tag.")

async def get_latest_running_scan(client : CxOneClient, projectid : str, branch : str) -> List[Response]:
        return await asyncio.gather(
            retrieve_last_scan(client, branch=branch, limit=1, project_ids=[projectid], scan_status="Running"), 
            retrieve_last_scan(client, branch=branch, limit=1, project_ids=[projectid], scan_status="Queued"))


async def should_scan(client : CxOneClient, project_repo : ProjectRepoConfig, branch : str) -> bool:
    if not await project_repo.is_scm_imported:
        running_scans = json_on_ok(await retrieve_list_of_scans(client, tags_keys="scheduled", branch=branch, 
                                                                project_id=project_repo.project_id, statuses=['Queued', 'Running']))
        if int(running_scans['filteredTotalCount']) == 0:
            return True
    else:
        # It currently isn't possible to tag a scan created in a project that was import from SCM, so just look
        # at the last scan in status Queued or Running.
        potential_running_scan, potential_queued_scan = await get_latest_running_scan(client, project_repo.project_id, branch)

        if not (project_repo.project_id in json_on_ok(potential_running_scan).keys() or project_repo.project_id in json_on_ok(potential_queued_scan).keys()):
            return True

    return False


async def create_name(project_name, project_id, repo_url, branch):
    return f"{project_name}:{project_id}:{repo_url}:{branch}"

async def find_scan_for_repo_scan(client : CxOneClient, projectid : str, branch : str) -> Union[ScanInspector, None]:
    running, queued = await get_latest_running_scan(client, projectid, branch)

    if running.ok and len(running.json()) > 0:
        json = json_on_ok(running)
    elif queued.ok and len(queued.json()) > 0:
        json = json_on_ok(queued)
    else:
        return None
    
    return ScanInspector(json[list(json.keys()).pop()])

async def check_source_fetch_complete(client : CxOneClient, scanid : str) -> bool:
    workflow = json_on_ok(await retrieve_scan_workflow(client, scanid))

    fetch_start = False
    fetch_complete = False

    # Use some logic when reviewing the workflow to understand if the
    # source fetch has completed.

    for entry in workflow:
        source = entry.get("Source", None)
        info = entry.get("Info", None)

        if source is None or info is None:
            continue

        if source == "fetch-sources-nv":
            if info.startswith("fetch-sources-nv started"):
                fetch_start = True
            elif info.startswith("fetch-sources-nv ended"):
                fetch_complete = True
            elif info.startswith("fetch-sources-nv Err"):
                fetch_complete = True
        elif source == "config-as-code-nv":
            if info.startswith("config-as-code-nv started"):
                fetch_complete = True
        elif source == "scans":
            if info.startswith("Scan Failed"):
                fetch_complete = True

        if fetch_start and fetch_complete:
            return True

    return False

async def main():
    try:
        wait_start = perf_counter_ns()
        with Semaphore(f"/cxone_scan", flags=O_CREAT, initial_value=get_threads_config()):
            args = parser.parse_args()

            __log.debug(f"Project {args.projectid} waited {(perf_counter_ns() - wait_start)/1000000:.2f}ms to acquire a scan submit thread.")
        
            tenant, oauth_id, oauth_secret = utils.load_secrets()
            assert not tenant is None
            assert not oauth_id is None
            assert not oauth_secret is None

            auth_endpoint, api_endpoint = utils.load_endpoints(tenant)
            assert auth_endpoint is not None and api_endpoint is not None


            ssl_verify = utils.get_ssl_verify()
            proxy = utils.get_proxy_config()

            

            tag = {__SCHEDULE_TAG: args.schedule} if args.schedule is not None else {__SCHEDULE_TAG : None}


            try:
                sem = Semaphore(f"/{utils.make_safe_name(args.projectid, args.branch)}", flags=O_CREAT, initial_value=1)
                sem.acquire(1)

                client = CxOneClient.create_with_oauth(oauth_id, oauth_secret, __scanagent__, auth_endpoint, 
                                    api_endpoint, 
                                    timeout=get_api_timeout_config(),
                                    retries=get_api_retries_config(),
                                    retry_delay_s=get_api_retry_delay_config(),
                                    ssl_verify=ssl_verify, proxy=proxy)
                try:
                    __log.debug(f"Semaphore acquired for {utils.make_safe_name(args.projectid, args.branch)}")
                    
                    project_repo = await ProjectRepoConfig.from_project_id(client, args.projectid)

                    # Do not submit a scheduled scan if a scheduled scan is already running.
                    if await should_scan(client, project_repo, args.branch):
                        scan_response = await ScanInvoker.scan_by_project_config(client, 
                                                                                 args.projectid, 
                                                                                 args.branch, 
                                                                                 create_engine_scan_config(args.engines),
                                                                                 tag)

                        if scan_response.ok:
                            __log.info(f"Scanning {await create_name(project_repo.name, args.projectid, args.repo, args.branch)}")

                            if get_fetch_throttle():
                                scan_insp = None
                                timeout_check = datetime.now()
                                overtime = False
                                while not overtime:
                                    overtime = (datetime.now() - timeout_check).seconds > get_fetch_timeout_config()

                                    if scan_insp is None:
                                        if await project_repo.is_scm_imported:
                                            scan_insp = await find_scan_for_repo_scan(client, args.projectid, args.branch)
                                        else:
                                            scan_insp = ScanInspector(scan_response.json())
                                    else:
                                        scan_insp = await ScanLoader.load(client, scan_insp.scan_id)

                                    if scan_insp is not None:
                                        __log.debug(f"Throttler monitoring scan {scan_insp.scan_id} for {await create_name(project_repo.name, args.projectid, args.repo, args.branch)}")

                                        if not scan_insp.executing:
                                            __log.debug("Scan %s is complete, exiting throttle loop after %d seconds.", scan_insp.scan_id, (datetime.now() - timeout_check).seconds)
                                            break

                                        if await check_source_fetch_complete(client, scan_insp.scan_id):
                                            __log.debug("Scan %s indicates source fetch is complete, exiting throttle loop after %d seconds.", 
                                                        scan_insp.scan_id, (datetime.now() - timeout_check).seconds)
                                            break

                                    else:
                                        __log.debug(f"Running scan not found for {await create_name(project_repo.name, args.projectid, args.repo, args.branch)}")

                                    await asyncio.sleep(__CHECK_DELAY_S)
                                
                                if overtime:
                                    __log.warning(f"Throttle loop is exiting after source fetch timeout for {await create_name(project_repo.name, args.projectid, args.repo, args.branch)}")
                        else:
                            __log.error(f"Failed to start scan for project {await create_name(project_repo.name, args.projectid, args.repo, args.branch)}: {scan_response.status_code}:{scan_response.json()}")

                    else:
                        __log.warning(f"Scheduled scan for {await create_name(project_repo.name, args.projectid, args.repo, args.branch)} is already running, skipping.")

                except Exception as ex:
                    __log.exception(ex)
                finally:
                    sem.release()


            except BusyError:
                __log.debug(f"Another process is handling scans for {await create_name(project_repo.name, args.projectid, args.repo, args.branch)}, skipping.")
            finally:
                sem.close()
    except SystemExit:
        pass

try:
    asyncio.run(main())
except Exception as ex:
    __log.exception(ex)
