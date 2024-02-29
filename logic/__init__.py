import logging, asyncio, utils
from cxone_api import paged_api, ProjectRepoConfig


class Scheduler:
    __log = logging.getLogger("Scheduler")


    @staticmethod
    async def __recursive_index_build(tree):
        by_gid = {}
        by_path = {}
        for item in tree:
            by_gid[item['id']] = item['path']
            by_path[item['path']] = item['id']
            child_by_gid, child_by_path = await Scheduler.__recursive_index_build(item['subGroups'])
            by_gid = by_gid | child_by_gid
            by_path = by_path | child_by_path
        
        return by_gid, by_path


    async def __get_group_index(self):
        group_json = (await self.__client.get_groups(briefRepresentation=True)).json()
        return await Scheduler.__recursive_index_build(group_json)


    async def __get_schedule_entry_from_tag(self, project_data, schedule_tag_value):
        if schedule_tag_value is None or len(schedule_tag_value) == 0:
            return None
        
        repo_details = ProjectRepoConfig(self.__client, project_data)
        
        elements = schedule_tag_value.split(":")

        if len(elements) > 0:
            ss = utils.ScheduleString(elements.pop(0), self.__policies)

            if ss.is_valid():
                branch = elements.pop(0) if len(elements) > 0 else ''
                if len(branch) == 0:
                    branch = await repo_details.primary_branch

                engines = utils.normalize_engine_set(elements.pop(0) if len(elements) > 0 else 'all')

                if (await repo_details.is_valid()):
                    return {project_data['id'] : [utils.ProjectSchedule(project_data['id'], ss, branch, engines, await repo_details.repo_url)]}
            else:
                Scheduler.__log.error(f"Project {project_data['id']}:{project_data['name']} has invalid schedule tag {schedule_tag_value}, skipping.")

        return None

    async def __get_tagged_project_schedule(self):
        Scheduler.__log.info("Begin: Load tagged project schedule")
        schedules = {}
        async for tagged_project in paged_api(self.__client.get_projects, "projects", tags_keys="schedule"):
            entry = await self.__get_schedule_entry_from_tag(tagged_project, tagged_project['tags']['schedule'])
            if entry is not None:
                schedules.update(entry)
        Scheduler.__log.info("End: Load tagged project schedule")
        return schedules

    async def __get_untagged_project_schedule(self):
        result = {}

        if not self.__group_schedules.empty or self.__default_schedule is not None:
            Scheduler.__log.info("Begin: Load untagged project schedule")

            by_gid = {}
            if not self.__group_schedules.empty:
                by_gid, _ = await self.__get_group_index()

            async for project in paged_api(self.__client.get_projects, "projects"):
                project_schedules = []

                # The schedule tag takes precedence
                if "schedule" in project['tags'].keys():
                    continue

                # Check that repo is defined and primary branch is defined
                repo_cfg = ProjectRepoConfig(self.__client, project)
                if await repo_cfg.is_valid():
                    # If the project matches a group, assign it the schedule for all matching groups.
                    for gid in project['groups']:
                        group_path = by_gid[gid]
                        ss = self.__group_schedules.get_schedule(group_path)
                    
                        if ss is not None:
                            project_schedules.append(utils.ProjectSchedule(project['id'], ss, 
                                                                        await repo_cfg.primary_branch, utils.normalize_engine_set('all'), await repo_cfg.repo_url))

                    if len(project_schedules) > 0:
                        result[project['id']] = project_schedules
                    elif self.__default_schedule is not None:
                        ss = utils.ScheduleString(self.__default_schedule, self.__policies)
                        if ss.is_valid():
                            result[project['id']] = [utils.ProjectSchedule(project['id'], ss.get_crontab_schedule(), 
                                                                                await repo_cfg.primary_branch, utils.normalize_engine_set('all'), await repo_cfg.repo_url)]
                else:
                    Scheduler.__log.warn(f"Project {project['id']}:{project['name']} has a misconfigured repo url or primary branch, not scheduled.")

            Scheduler.__log.info("End: Load untagged project schedule")
        else:
            Scheduler.__log.info("No untagged schedules loaded")

        return result


    @staticmethod
    async def start(client, default_schedule, group_schedules, policies):

        ret_sched = Scheduler()
        ret_sched.__client = client
        ret_sched.__default_schedule = default_schedule
        ret_sched.__group_schedules = group_schedules
        ret_sched.__policies = policies

        tagged, grouped = await asyncio.gather(ret_sched.__get_tagged_project_schedule(), ret_sched.__get_untagged_project_schedule())

        # It is possible that modifications were done to projects while compiling schedules.  If there are intersections,
        # the tagged project takes precedence.
        intersection = list(set(tagged.keys()) & set(grouped.keys()) )

        for k in intersection:
            grouped.pop(k, None)
        
        ret_sched.__schedule = tagged | grouped

        utils.write_schedule(ret_sched.__schedule)

        return ret_sched


