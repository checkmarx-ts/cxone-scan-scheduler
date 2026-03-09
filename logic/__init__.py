import logging, utils, asyncio
from scan import ScanExecutor
from cxone_api.util import page_generator
from cxone_api.high.projects import ProjectRepoConfig
from cxone_api.high.access_mgmt.user_mgmt import Groups
from cxone_api.low.projects import retrieve_list_of_projects
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from utils import (normalize_repo_enabled_engines, 
                   get_threads_config, 
                   ProjectSchedule)
from time import perf_counter_ns
from datetime import timedelta


class Scheduler:
    
    __log = logging.getLogger("Scheduler")

    async def __get_schedule_entry_from_tag(self, project_data, schedule_tag_value, bad_cb):
        if schedule_tag_value is None or len(schedule_tag_value) == 0:
            if bad_cb is not None:
                bad_cb(project_data['id'], "No schedule tag value.")
            return None
        
        repo_details = await ProjectRepoConfig.from_project_json(self.__client, project_data)

        if await repo_details.is_scm_imported and await repo_details.scm_creds_expired:
            if bad_cb is not None:
                bad_cb(project_data['id'], "Imported repository credentials have expired.")
            return None
        
        elements = schedule_tag_value.split(":")

        if len(elements) > 0:
            ss = utils.ScheduleString(elements.pop(0), self.__policies)

            if ss.is_valid():
                branch = elements.pop(0) if len(elements) > 0 else ''
                if len(branch) == 0:
                    branch = await repo_details.primary_branch
                
                if branch is None:
                    if bad_cb is not None:
                        bad_cb(project_data['id'], "Scan branch can't be determined.")
                    return None
                
                engines_from_tag = elements.pop(0) if len(elements) > 0 else None
                engines = None

                if engines_from_tag is None:
                    engines = normalize_repo_enabled_engines(await repo_details.get_enabled_scanners(branch))

                if engines is None or len(engines) == 0:
                    engines = utils.normalize_selected_engines_from_tag(engines_from_tag if engines_from_tag is not None else 'all', 
                                                                        await repo_details.is_scm_imported)

                if engines is None:
                    if bad_cb is not None:
                        bad_cb(project_data['id'], "Scan engines can't be determined.")
                    return None

                repo_url = await repo_details.repo_url
                if repo_url is None:
                    if bad_cb is not None:
                        bad_cb(project_data['id'], "Repository URL is not set.")
                    return None

                if repo_url is not None and branch is not None:
                    return {project_data['id'] : [utils.ProjectSchedule(project_data['id'], ss, branch, engines, await repo_details.repo_url)]}
            else:
                Scheduler.__log.error(f"Project {project_data['id']}:{project_data['name']} has invalid schedule tag {schedule_tag_value}, skipping.")
                if bad_cb is not None:
                    bad_cb(project_data['id'], f"Bad schedule tag value.")

        return None


    async def __get_schedule_entry_no_tag(self, bad_cb, group_index, project_json):
        project_schedules = []

        # Check that repo is defined and primary branch is defined
        repo_cfg = await ProjectRepoConfig.from_project_json(self.__client, project_json)
        if (await repo_cfg.repo_url is not None) and (await repo_cfg.primary_branch is not None):
            # If the project matches a group, assign it the schedule for all matching groups.
            for gid in project_json['groups']:
                g_desc = await group_index.get_by_id(gid)

                if g_desc is not None:
                    ss = self.__group_schedules.get_schedule(str(g_desc.path))
                
                    if ss is not None:
                        project_schedules.append(utils.ProjectSchedule(project_json['id'], ss, 
                            await repo_cfg.primary_branch, 
                            utils.normalize_selected_engines_from_tag('all', await repo_cfg.is_scm_imported), 
                            await repo_cfg.repo_url))

            if len(project_schedules) > 0:
                return {project_json['id'] : project_schedules}
            elif self.__default_schedule is not None:
                ss = utils.ScheduleString(self.__default_schedule, self.__policies)
                if ss.is_valid():
                    return {project_json['id'] : [utils.ProjectSchedule(project_json['id'], 
                        ss.get_crontab_schedule(), 
                        await repo_cfg.primary_branch, 
                        utils.normalize_selected_engines_from_tag('all', await repo_cfg.is_scm_imported),
                        await repo_cfg.repo_url)]}
        else:
            if self.__default_schedule is not None and bad_cb is not None:
                bad_cb(project_json['id'], f"Project [{project_json['name']}] has a misconfigured repo url or primary branch.")

    async def __get_changed_projects(self, new_schedule):
        check_projects = set(new_schedule.keys()) & set(self.__the_schedule.keys())

        result = {}
        for k in check_projects:
            if not len(new_schedule[k]) == len(self.__the_schedule[k]):
                result[k] = new_schedule[k]
            else:
                new_schedule_comps = set([str(x) for x in new_schedule[k]])
                old_schedule_comps = set([str(x) for x in self.__the_schedule[k]])
                if len(new_schedule_comps - old_schedule_comps) > 0:
                    result[k] = new_schedule[k]

        return result

    async def refresh_schedule(self):
        new_schedule = await self.__load_schedule()

        # Schedules that are in new_schedule but not in the current schedule are new
        # and can be written immediately.
        new_scheduled_projects = set(new_schedule.keys()) - set(self.__the_schedule.keys())
        new_schedules = {k:new_schedule[k] for k in new_scheduled_projects}

        for sched_list in new_schedules.values():
            for new_sched in sched_list:
                self.__add_job(new_sched)

        self.__log.debug(f"Detected {len(new_scheduled_projects)} new project schedules")
        
        # Schedules that are in the current schedule but not in the new schedule can
        # be removed.
        removed_projects = set(self.__the_schedule.keys()) - set(new_schedule.keys())

        self.__log.debug(f"Deleting {len(removed_projects)} project schedules")
        for removed in removed_projects:
            if removed in self.__job_cache.keys():
                for job in self.__job_cache[removed]:
                    job.remove()
                del self.__job_cache[removed]

            self.__the_schedule.pop(removed, None)

        # Schedules that still exist should be checked for changes.  Any changed
        # schedules need to be re-written.
        changed_schedule = await self.__get_changed_projects(new_schedule)
        self.__log.debug(f"Changing {len(changed_schedule)} project schedules")
        for k in changed_schedule.keys():
            self.__the_schedule.pop(k, None)
            self.__the_schedule[k] = changed_schedule[k]

            if k in self.__job_cache.keys():
                for job in self.__job_cache[k]:
                    job.remove()
                del self.__job_cache[k]
            
            for sched in self.__the_schedule[k]:
                self.__add_job(sched)


        self.__the_schedule = self.__the_schedule | new_schedules

        return len(new_scheduled_projects), len(removed_projects), len(changed_schedule.keys())

    @property
    def scheduled_scans(self):
        return len(self.__the_schedule.keys())
        

    async def __load_schedule(self, bad_cb = None):
        load_start = perf_counter_ns()
        Scheduler.__log.debug("Begin: Load project schedule")

        schedule = {}
        
        group_index = Groups(self.__client)

        if not self.__group_schedules.empty or self.__default_schedule is not None:
            tag_args = {}
        else:
            tag_args = {'tags_keys' : 'schedule'}

        async for project in page_generator(retrieve_list_of_projects, "projects", client=self.__client, limit=100, **tag_args):
            if "schedule" in project['tags'].keys():
                entry = await self.__get_schedule_entry_from_tag(project, project['tags']['schedule'], bad_cb)
                if entry is not None:
                    schedule.update(entry)
                else:
                    Scheduler.__log.debug(f"NO SCHEDULE ENTRY: {project}")
            else:
                entry = await self.__get_schedule_entry_no_tag(bad_cb, group_index, project)
                if entry is not None:
                    schedule.update(entry)

        Scheduler.__log.debug("End: Load project schedule")
        Scheduler.__log.info(f"Schedule load time: {timedelta(microseconds=(perf_counter_ns() - load_start)/1000)}")

        return schedule


    @staticmethod
    async def __initialize(client, default_schedule, group_schedules, policies):
        ret_sched = Scheduler()
        ret_sched.__client = client
        ret_sched.__group_schedules = group_schedules
        ret_sched.__policies = policies
        ret_sched.__default_schedule = None
        ret_sched.__threads = asyncio.Semaphore(get_threads_config())

        ret_sched.__scheduler = AsyncIOScheduler(job_defaults={"coalesce" : True, "misfire_grace_time" : None})
        ret_sched.__scheduler.start()
        ret_sched.__trigger_cache = {}

        for trigger in policies:
            if policies[trigger] not in ret_sched.__trigger_cache.keys():
                ret_sched.__trigger_cache[policies[trigger]] = CronTrigger.from_crontab(policies[trigger])

        ret_sched.__job_cache = {}
        
        if default_schedule is not None and default_schedule in ret_sched.__policies.keys():
            ret_sched.__default_schedule = default_schedule
        elif default_schedule is None:
            Scheduler.__log.info("No default schedule policy has been defined.")
        else:
            Scheduler.__log.error(f"Default schedule [{default_schedule}] is not a valid policy.")

        return ret_sched
    
    @staticmethod
    async def audit(client, default_schedule, group_schedules, policies, bad_callback):
        schedule = await Scheduler.__initialize(client, default_schedule, group_schedules, policies)
        return await schedule.__load_schedule(bad_callback)

    def __add_job(self, sched : ProjectSchedule) -> None:
        async def _exec_wrapper(executor : ScanExecutor, **kwargs):
            await executor(**kwargs)

        if sched.project_id not in self.__job_cache.keys():
            self.__job_cache[sched.project_id] = []

        self.__job_cache[sched.project_id].append(self.__scheduler.add_job(
                    _exec_wrapper, 
                    self.__trigger_cache[sched.schedule], name=str(sched),
                    kwargs = {"executor" : ScanExecutor(self.__client), "sched" : sched, "threads" : self.__threads} ))

    @staticmethod
    async def start(client, default_schedule, group_schedules, policies):

        ret_sched = await Scheduler.__initialize(client, default_schedule, group_schedules, policies)
        ret_sched.__the_schedule = await ret_sched.__load_schedule(None)

        for pid in ret_sched.__the_schedule:
            for scan_sched in ret_sched.__the_schedule[pid]:
                ret_sched.__add_job(scan_sched)

        return ret_sched


