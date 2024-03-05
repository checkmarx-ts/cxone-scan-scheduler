#!/usr/local/bin/python
import logging, argparse, utils, asyncio
from cxone_api import CxOneClient
from posix_ipc import Semaphore, BusyError, O_CREAT

utils.configure_normal_logging()
__log = logging.getLogger("scan executor")


parser = argparse.ArgumentParser(description="A program to execute scans in CheckmarxOne as a Scheduler cron job.")

parser.add_argument('--projectid', '-p', action='store', type=str, required=True, dest="projectid", help="The CxOne project id found in the tenant.")
parser.add_argument('--engine', '-e', action='append', type=str, required=True, dest="engines", help="The engines to use for the scan.")
parser.add_argument('--repo', '-r', action='store', type=str, required=True, dest="repo", help="The code repository URL.")
parser.add_argument('--branch', '-b', action='store', type=str, required=True, dest="branch", help="The code repository URL.")
parser.add_argument('--schedule', '-s', action='store', type=str, required=False, default='unknown', dest="schedule", help="The schedule used to invoke the scan.")



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

        client = CxOneClient(oauth_id, oauth_secret, agent, version, auth_endpoint, 
                            api_endpoint, ssl_verify=ssl_verify, proxy=proxy)
        

        tag = {"scheduled": args.schedule} if args.schedule is not None else {"scheduled" : None}

        try:
            sem = Semaphore(f"/{utils.make_safe_name(args.projectid, args.branch)}", flags=O_CREAT, initial_value=1)
            sem.acquire(1)

            try:
                __log.debug(f"Semaphore acquired for {utils.make_safe_name(args.projectid, args.branch)}")

                # Do not submit a scheduled scan if a scheduled scan is already running.
                scans = (await client.get_scans(tags_keys="scheduled", branch=args.branch, project_id=args.projectid, statuses=['Queued', 'Running'])).json()

                if scans['filteredTotalCount'] == 0:
                    scan_spec = {
                        "type" : "git",
                        "handler" : {
                            "branch" : args.branch,
                            "repoUrl" : args.repo
                        },
                        "project" : {
                            "id" : args.projectid,
                        },
                        "config" : [{ "type" : x, "value" : {} } for x in args.engines],
                        "tags" : tag
                    }
                   
                    
                    response = await client.execute_scan(scan_spec)
                    if response.ok:
                        __log.info(f"Scanning project {args.projectid} branch {args.branch}")
                    else:
                        __log.error(f"Failed to start scan for project {args.projectid} branch {args.branch}: {response.status_code}:{response.reason}")


                else:
                    __log.warning(f"Scheduled project for {args.projectid} branch {args.branch} is already running, skipping.")

            except Exception:
                pass
            finally:
                sem.release()

            pass
        

        except BusyError:
            __log.debug(f"Another process is handling scans for projectid {args.projectid} branch {args.branch}, skipping.")
        finally:
            sem.close()

    except SystemExit:
        pass

try:
    asyncio.run(main())
except Exception as ex:
    __log.exception(ex)
