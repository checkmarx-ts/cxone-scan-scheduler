from cxone_api import CxOneClient
from cxone_api.high.scans import ScanInvoker, ScanInspector, ScanLoader
from cxone_api.high.projects import ProjectRepoConfig
from cxone_api.low.projects import retrieve_last_scan
from cxone_api.low.scans import retrieve_list_of_scans, retrieve_scan_workflow
from cxone_api.util import json_on_ok
from utils import (create_engine_scan_config, 
                   get_recent_scan_hours_config, 
                   get_fetch_timeout_config,
                   get_fetch_throttle, ProjectSchedule)
from typing import List, Union
import asyncio, logging
from datetime import datetime, timedelta, timezone
from requests import Response


class ScanExecutor:
  __CHECK_DELAY_S = 30
  __SCHEDULE_TAG = "scheduled"

  @classmethod
  def log(clazz):
      return logging.getLogger("Scanner")

  def __init__(self, client : CxOneClient):
    self.__client = client


  async def __call__(self, sched : ProjectSchedule, threads : asyncio.Semaphore):
    async with threads:
        try:
            project_repo = await ProjectRepoConfig.from_project_id(self.__client, sched.project_id)
            safe_name = ScanExecutor.__create_name(project_repo.name, sched.project_id, sched.repo_url, sched.branch)

            tag = {ScanExecutor.__SCHEDULE_TAG: sched.schedule} if sched.schedule is not None else {ScanExecutor.__SCHEDULE_TAG : None}


            # Do not submit a scheduled scan if a scheduled scan is already running.
            if await self.__should_scan(project_repo, sched.branch):
                scan_response = await ScanInvoker.scan_by_project_config(self.__client, 
                                                                        sched.project_id, 
                                                                        sched.branch, 
                                                                        create_engine_scan_config(sched.engines),
                                                                        tag)

                if scan_response.ok:
                    ScanExecutor.log().info(f"Scanning {safe_name}")

                    if get_fetch_throttle():
                        scan_insp = None
                        timeout_check = datetime.now()
                        overtime = False
                        while not overtime:
                            overtime = (datetime.now() - timeout_check).seconds > get_fetch_timeout_config()

                            if scan_insp is None:
                                if await project_repo.is_scm_imported:
                                    scan_insp = await self.__find_scan_for_repo_scan(sched.project_id, sched.branch)
                                else:
                                    scan_insp = ScanInspector(scan_response.json())
                            else:
                                scan_insp = await ScanLoader.load(self.__client, scan_insp.scan_id)

                            if scan_insp is not None:
                                ScanExecutor.log().debug(f"Throttler monitoring scan {scan_insp.scan_id} for {safe_name}")

                                if not scan_insp.executing:
                                    ScanExecutor.log().debug("Scan %s is complete, exiting throttle loop after %d seconds.", scan_insp.scan_id, (datetime.now() - timeout_check).seconds)
                                    break

                                if await self.__check_source_fetch_complete(scan_insp.scan_id):
                                    ScanExecutor.log().debug("Scan %s indicates source fetch is complete, exiting throttle loop after %d seconds.", 
                                                scan_insp.scan_id, (datetime.now() - timeout_check).seconds)
                                    break

                            else:
                                ScanExecutor.log().debug(f"Running scan not found for {safe_name}")

                            await asyncio.sleep(ScanExecutor.__CHECK_DELAY_S)
                        
                        if overtime:
                            ScanExecutor.log().warning(f"Throttle loop is exiting after source fetch timeout for {safe_name}")
                else:
                    ScanExecutor.log().error(f"Failed to start scan for project {safe_name}: {scan_response.status_code}:{scan_response.json()}")

            else:
                ScanExecutor.log().warning(f"Scheduled scan for {safe_name} skipped.")

        except Exception as ex:
            ScanExecutor.log().exception(ex)

  @staticmethod
  def __create_name(project_name, project_id, repo_url, branch):
      return f"{project_name}:{project_id}:{repo_url}:{branch}"

  async def __get_latest_running_scan(self, projectid : str, branch : str) -> List[Response]:
          return await asyncio.gather(
              retrieve_last_scan(self.__client, branch=branch, limit=1, project_ids=[projectid], scan_status="Running"), 
              retrieve_last_scan(self.__client, branch=branch, limit=1, project_ids=[projectid], scan_status="Queued"))



  async def __should_scan(self, project_repo : ProjectRepoConfig, branch : str) -> bool:
      running_scan = False

      if not await project_repo.is_scm_imported:
          running_scans = json_on_ok(await retrieve_list_of_scans(self.__client, tags_keys="scheduled", branch=branch, 
                                                                  project_id=project_repo.project_id, limit=1, statuses=['Queued', 'Running']))
          if int(running_scans['filteredTotalCount']) != 0:
              running_scan = True
      else:
          # It currently isn't possible to tag a scan created in a project that was import from SCM, so just look
          # at the last scan in status Queued or Running.
          potential_running_scan, potential_queued_scan = await self.__get_latest_running_scan(project_repo.project_id, branch)

          if project_repo.project_id in json_on_ok(potential_running_scan).keys() or project_repo.project_id in json_on_ok(potential_queued_scan).keys():
              running_scan = True
      
      if not running_scan and get_recent_scan_hours_config() > 0:
          previous_time = datetime.now(timezone.utc) - timedelta(hours=get_recent_scan_hours_config())

          previous_scans = json_on_ok(await retrieve_list_of_scans(self.__client, branch=branch, project_id=project_repo.project_id, 
                                                                  statuses=['Completed'], limit=1, from_date=previous_time.isoformat()))
          if int(previous_scans['filteredTotalCount']) != 0:
              return False

      return not running_scan


  async def __find_scan_for_repo_scan(self, projectid : str, branch : str) -> Union[ScanInspector, None]:
      running, queued = await self.__get_latest_running_scan(projectid, branch)

      if running.ok and len(running.json()) > 0:
          json = json_on_ok(running)
      elif queued.ok and len(queued.json()) > 0:
          json = json_on_ok(queued)
      else:
          return None
      
      return ScanInspector(json[list(json.keys()).pop()])

  async def __check_source_fetch_complete(self, scanid : str) -> bool:
      workflow = json_on_ok(await retrieve_scan_workflow(self.__client, scanid))

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
