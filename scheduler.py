#!/usr/bin/python3
import sys, os, logging, utils
from __agent__ import __schedagent__

if sys.argv[0].lower().startswith("audit") or \
    (len (sys.argv) > 1 and sys.argv[1] is not None and sys.argv[1].lower().startswith("audit")):
    is_audit = True
    utils.configure_audit_logging()
else:
    is_audit = False
    utils.configure_normal_logging()

import asyncio, aiofiles, time
from cxone_api import CxOneClient
from cxone_api.exceptions import CommunicationException
from logic import Scheduler
from utils import (get_api_timeout_config, 
                   get_api_retry_delay_config, 
                   get_api_retries_config)


__log = logging.getLogger("scheduler daemon")
__log.info("Scheduler starting")

while True:
    try:
        __log.debug("Loading configuration")
        tenant, oauth_id, oauth_secret = utils.load_secrets()
        assert not tenant is None
        assert not oauth_id is None
        assert not oauth_secret is None

        auth_endpoint, api_endpoint = utils.load_endpoints(tenant)
        assert auth_endpoint is not None and api_endpoint is not None

        ssl_verify = utils.get_ssl_verify()
        proxy = utils.get_proxy_config()

        client = CxOneClient.create_with_oauth(oauth_id, oauth_secret, __schedagent__, auth_endpoint, 
                            api_endpoint, 
                            timeout=get_api_timeout_config(),
                            retries=get_api_retries_config(),
                            retry_delay_s=get_api_retry_delay_config(),
                            ssl_verify=ssl_verify, proxy=proxy)

        policies = utils.load_policies()
        __log.debug(f"Policies: {policies}")

        default_schedule = utils.load_default_schedule()
        __log.debug(f"Default Schedule: {default_schedule}")

        group_schedules = utils.load_group_schedules(policies)
        __log.debug(f"Group Schedules: {group_schedules}")

        update_delay = utils.load_schedule_update_delay()
        __log.debug(f"Update Delay: {update_delay}")


        __log.debug("Configuration loaded")

        async def log_fifo():
            if os.path.exists("/opt/cxone/logfifo"):
                __log.debug("Running background fifo reader")
                while True:
                    async with aiofiles.open("/opt/cxone/logfifo", "rt", buffering=1) as log:
                        async for line in log:
                            if len(line) > 0:
                                print(line.strip())


        async def scheduler():
            the_scheduler = await Scheduler.start(client, default_schedule, group_schedules, policies)

            # This task will never end
            logtask = asyncio.create_task(log_fifo())

            __log.info("Scheduler loop started")
            short_delay = False
            while True:
                __log.info(f"Projects with scheduled scans: {the_scheduler.scheduled_scans}")
                await asyncio.sleep(update_delay if not short_delay else 90)
                __log.info("Updating schedule...")
                try:
                    new, removed, changed = await the_scheduler.refresh_schedule()
                    short_delay = False
                    __log.info(f"Schedule changes: New: {new} Removed: {removed} Changed: {changed}")
                except CommunicationException as ex:
                    __log.exception(ex)
                    short_delay = True
                except Exception as gex:
                    __log.exception(gex)

        async def audit():
            print('"ProjectId","State","Details"')

            def skipped_entry_cb(project_id, reason):
                print(f'"{project_id}","SKIPPED","{reason}"')

            for entry in (await Scheduler.audit(client, default_schedule, group_schedules, policies, skipped_entry_cb)).values():
                for sched in entry:
                    clean_sched = str(sched).replace("'", "")
                    print(f'"{sched.project_id}","SCHEDULED","{clean_sched}"')

        if is_audit:
            try:
                audit_log = logging.getLogger("audit")
                asyncio.run(audit())
            except BaseException as ex:
                audit_log.exception(ex)
            finally:
                break
        else:
            asyncio.run(scheduler())

    except Exception as ex:
        __log.exception(ex)
        __log.info("Unhandled exception, retrying after delay.")
        time.sleep(90)
