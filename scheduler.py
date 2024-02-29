#!/bin/python
import logging, utils, asyncio
from cxone_api import AuthRegionEndpoints, ApiRegionEndpoints, CxOneClient, paged_api, ProjectRepoConfig

__log = logging.getLogger("scheduler")
__log.info("Scheduler starting")

try:
    __log.debug("Loading configuration")
    tenant, oauth_id, oauth_secret = utils.load_secrets()
    assert not tenant is None
    assert not oauth_id is None
    assert not oauth_secret is None

    region = utils.load_region()
    assert not region is None

    policies = utils.load_policies()
    default_schedule = utils.load_default_schedule()
    group_schedules = utils.load_group_schedules(policies)

    auth_endpoint = AuthRegionEndpoints[region](tenant)
    api_endpoint = ApiRegionEndpoints[region]()

    ssl_verify = utils.get_ssl_verify()
    proxy = utils.get_proxy_config()

    __log.debug("Configuration loaded")

    agent = "CxOne Scheduler"
    version = None
    with open("version.txt", "rt") as ver:
        version = ver.readline().strip()

    client = CxOneClient(oauth_id, oauth_secret, agent, version, auth_endpoint, 
                        api_endpoint, ssl_verify=ssl_verify, proxy=proxy)


    async def get_schedule_entry_from_tag(project_data, schedule_tag_value):
        if schedule_tag_value is None or len(schedule_tag_value) == 0:
            return None
        
        repo_details = ProjectRepoConfig(client, project_data)
        
        elements = schedule_tag_value.split(":")

        if len(elements) > 0:
            ss = utils.ScheduleString(elements.pop(0), policies)

            if ss.is_valid():
                branch = elements.pop(0) if len(elements) > 0 else ''
                if len(branch) == 0:
                    branch = await repo_details.primary_branch

                engines = utils.normalize_engine_set((elements.pop(0) if len(elements) > 0 else 'all'))

                if (await repo_details.is_valid()):
                    return {project_data['id'] : [utils.ProjectSchedule(project_data['id'], ss, branch, engines, await repo_details.repo_url)]}
            else:
                __log.error(f"Project {project_data['id']}:{project_data['name']} has invalid schedule tag {schedule_tag_value}, skipping.")

        return None

    async def get_tagged_project_schedule():
        __log.info("Begin: Load tagged project schedule")
        schedules = {}
        async for tagged_project in paged_api(client.get_projects, "projects", tags_keys="schedule"):
            entry = await get_schedule_entry_from_tag(tagged_project, tagged_project['tags']['schedule'])
            if entry is not None:
                schedules.update(entry)
        __log.info("End: Load tagged project schedule")
        return schedules
    
    async def recursive_index_build(tree):
        by_gid = {}
        by_path = {}
        for item in tree:
            by_gid[item['id']] = item['path']
            by_path[item['path']] = item['id']
            child_by_gid, child_by_path = await recursive_index_build(item['subGroups'])
            by_gid = by_gid | child_by_gid
            by_path = by_path | child_by_path
        
        return by_gid, by_path

    async def get_group_index():
        group_json = (await client.get_groups(briefRepresentation=True)).json()
        return await recursive_index_build(group_json)

    async def get_untagged_project_schedule():
        result = {}

        if not group_schedules.empty or default_schedule is not None:
            __log.info("Begin: Load untagged project schedule")

            by_gid = {}
            if not group_schedules.empty:
                by_gid, _ = await get_group_index()

            async for project in paged_api(client.get_projects, "projects"):
                project_schedules = []

                # The schedule tag takes precedence
                if "schedule" in project['tags'].keys():
                    continue

                # Check that repo is defined and primary branch is defined
                repo_cfg = ProjectRepoConfig(client, project)
                if await repo_cfg.is_valid():
                    # If the project matches a group, assign it the schedule for all matching groups.
                    for gid in project['groups']:
                        group_path = by_gid[gid]
                        ss = group_schedules.get_schedule(group_path)
                    
                        if ss is not None:
                            project_schedules.append(utils.ProjectSchedule(project['id'], ss, 
                                                                        await repo_cfg.primary_branch, 'all', await repo_cfg.repo_url))

                    if len(project_schedules) > 0:
                        result[project['id']] = project_schedules
                    elif default_schedule is not None:
                        ss = utils.ScheduleString(default_schedule, policies)
                        if ss.is_valid():
                            result[project['id']] = [utils.ProjectSchedule(project['id'], ss.get_crontab_schedule(), 
                                                                                await repo_cfg.primary_branch, 'all', await repo_cfg.repo_url)]
                else:
                    __log.warn(f"Project {project['id']}:{project['name']} has a misconfigured repo url or primary branch, not scheduled.")

            __log.info("End: Load untagged project schedule")
        else:
            __log.info("No untagged schedules loaded")

        return result


    async def main():
        tagged, grouped = await asyncio.gather(get_tagged_project_schedule(), get_untagged_project_schedule())

        # It is possible that modifications were done to projects while compiling schedules.  If there are intersections,
        # the tagged project takes precedence.
        intersection = list(set(tagged.keys()) & set(grouped.keys()) )

        for k in intersection:
            grouped.pop(k, None)
        
        theschedule = tagged | grouped

        print(theschedule)



    asyncio.run(main())

except Exception as ex:
    __log.exception(ex)
