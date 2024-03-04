#!/usr/local/bin/python
import logging, utils, asyncio, aiofiles, os
from cxone_api import AuthRegionEndpoints, ApiRegionEndpoints, CxOneClient, paged_api, ProjectRepoConfig, CommunicationException, AuthException
from logic import Scheduler

__log = logging.getLogger("scheduler daemon")
__log.info("Scheduler starting")

try:
    __log.debug("Loading configuration")
    tenant, oauth_id, oauth_secret = utils.load_secrets()
    assert not tenant is None
    assert not oauth_id is None
    assert not oauth_secret is None

    region = utils.load_region()
    assert not region is None
    auth_endpoint = AuthRegionEndpoints[region](tenant)
    api_endpoint = ApiRegionEndpoints[region]()
    ssl_verify = utils.get_ssl_verify()
    proxy = utils.get_proxy_config()

    agent = "CxOne Scheduler"
    version = None
    with open("version.txt", "rt") as ver:
        version = ver.readline().strip()

    client = CxOneClient(oauth_id, oauth_secret, agent, version, auth_endpoint, 
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


    async def main():

        the_scheduler = await Scheduler.start(client, default_schedule, group_schedules, policies)

        # This task will never end
        logtask = asyncio.create_task(log_fifo())

        __log.info("Scheduler loop started")
        short_delay = False
        while True:
            await asyncio.sleep(update_delay if not short_delay else 90)
            __log.info("Updating schedule...")
            try:
                await the_scheduler.refresh_schedule()
                short_delay = False
            except CommunicationException as ex:
                __log.exception(ex)
                short_delay = True
            except Exception as gex:
                __log.exception(gex)

    asyncio.run(main())

except Exception as ex:
    __log.exception(ex)
