#!/usr/bin/python3
import logging, argparse, utils, asyncio
from cxone_api import CxOneClient
from cxone_api.scanning import ScanInvoker
from cxone_api.projects import ProjectRepoConfig
from cxone_api.util import json_on_ok
from posix_ipc import Semaphore, BusyError, O_CREAT

utils.configure_normal_logging()
__log = logging.getLogger("scan executor")


parser = argparse.ArgumentParser(description="A program to execute scans in CheckmarxOne as a Scheduler cron job.")

parser.add_argument('--projectid', '-p', action='store', type=str, required=True, dest="projectid", help="The CxOne project id found in the tenant.")
parser.add_argument('--engine', '-e', action='append', type=str, required=True, dest="engines", help="The engines to use for the scan.")
parser.add_argument('--repo', '-r', action='store', type=str, required=True, dest="repo", help="The code repository URL.")
parser.add_argument('--branch', '-b', action='store', type=str, required=True, dest="branch", help="The code repository URL.")
parser.add_argument('--schedule', '-s', action='store', type=str, required=False, default='unknown', dest="schedule", help="The schedule string assigned to the 'scheduled' scan tag.")


async def should_scan(client : CxOneClient, project_repo : ProjectRepoConfig, branch : str) -> bool:
    if not await project_repo.is_scm_imported:
        running_scans = json_on_ok(await client.get_scans(tags_keys="scheduled", branch=branch, project_id=project_repo.project_id, statuses=['Queued', 'Running']))
        if int(running_scans['filteredTotalCount']) == 0:
            return True
    else:
        # It currently isn't possible to tag a scan created in a project that was import from SCM, so just look
        # at the last scan in status Queued or Running.
        potential_running_scan, potential_queued_scan = await asyncio.gather(
            client.get_projects_last_scan(branch=branch, limit=1, project_ids=[project_repo.project_id], scan_status="Running"), 
            client.get_projects_last_scan(branch=branch, limit=1, project_ids=[project_repo.project_id], scan_status="Queued")
            )

        if not (project_repo.project_id in json_on_ok(potential_running_scan).keys() or project_repo.project_id in json_on_ok(potential_queued_scan).keys()):
            return True

    return False


async def create_name(project_name, project_id, repo_url, branch):
    return f"{project_name}:{project_id}:{repo_url}:{branch}"

async def main():
    try:
        args = parser.parse_args()
       
        tenant, oauth_id, oauth_secret = utils.load_secrets()
        assert not tenant is None
        assert not oauth_id is None
        assert not oauth_secret is None

        auth_endpoint, api_endpoint = utils.load_endpoints(tenant)
        assert auth_endpoint is not None and api_endpoint is not None


        ssl_verify = utils.get_ssl_verify()
        proxy = utils.get_proxy_config()

        agent = "CxCron"
        version = None
        with open("version.txt", "rt") as ver:
            version = ver.readline().strip()

        client = CxOneClient.create_with_oauth(oauth_id, oauth_secret, f"{agent}/{version}", auth_endpoint, 
                            api_endpoint, ssl_verify=ssl_verify, proxy=proxy)
        

        tag = {"scheduled": args.schedule} if args.schedule is not None else {"scheduled" : None}

        try:
            sem = Semaphore(f"/{utils.make_safe_name(args.projectid, args.branch)}", flags=O_CREAT, initial_value=1)
            sem.acquire(1)

            try:
                __log.debug(f"Semaphore acquired for {utils.make_safe_name(args.projectid, args.branch)}")
                
                project_repo = await ProjectRepoConfig.from_project_id(client, args.projectid)

                # Do not submit a scheduled scan if a scheduled scan is already running.
                if await should_scan(client, project_repo, args.branch):

                    scan_response = await ScanInvoker.scan_get_response(client, project_repo, args.branch, args.engines, tag)

                    if scan_response.ok:
                        __log.info(f"Scanning {await create_name(project_repo.name, args.projectid, args.repo, args.branch)}")
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
