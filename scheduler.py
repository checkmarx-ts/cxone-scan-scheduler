#!/usr/local/bin/python
import sys, os, logging, utils

if sys.argv[0].lower().startswith("audit"):
    is_audit = True
    utils.configure_audit_logging()
else:
    is_audit = False
    utils.configure_normal_logging()

import asyncio, aiofiles, time
from cxone_api import CxOneClient, paged_api, CommunicationException
from logic import Scheduler


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

        agent = "CxOneScheduler"
        version = None
        with open("version.txt", "rt") as ver:
            version = ver.readline().strip()

        client = CxOneClient.create_with_oauth(oauth_id, oauth_secret, agent, version, auth_endpoint, 
                            api_endpoint, ssl_verify=ssl_verify, proxy=proxy)


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
                    print(f'"{sched.project_id}","SCHEDULED","{str(sched).replace("'", "")}"')

        if is_audit:
            asyncio.run(audit())
            break
        else:
            asyncio.run(scheduler())

    except Exception as ex:
        __log.exception(ex)
        __log.info("Unhandled exception, retrying after delay.")
        time.sleep(90)
