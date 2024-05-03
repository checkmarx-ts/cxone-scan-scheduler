import asyncio
from util import CloneUrlParser

class ProjectRepoConfig:

    def __init__(self, cxone_client, project_config):
        self.__client = cxone_client
        self.__project_data = project_config
        self.__fetched_undocumented_config = False
        self.__fetched_repomgr_config = False
        self.__fetched_scm_config = False
        self.__lock = asyncio.Lock()
   
    async def __get_undocumented_config(self):
        # The documented project API seems to have a bug and does not return the repoUrl.  The undocumented
        # API used by the UI has it.  The undocumented API will no longer be called when the project
        # API is fixed.
        async with self.__lock:
            if not self.__fetched_undocumented_config:
                self.__fetched_undocumented_config = True
                self.__undocumented_config = (await self.__client.get_project_configuration(self.project_id)).json()

        return self.__undocumented_config
        
    async def __get_repourl_from_undocumented_config(self):
        for entry in await self.__get_undocumented_config():
            if entry['key'] == "scan.handler.git.repository":
                return entry['value']
        
        return None

    async def __get_repomgr_config(self):
        # Projects imported from the SCM have their repo credentials stored in the repo-manager
        if not "repoId" in self.__project_data.keys(): 
            return None

        async with self.__lock:
            if not self.__fetched_repomgr_config:
                self.__fetched_repomgr_config = True
                repoId = self.__project_data['repoId']
                self.__repomgr_config = (await self.__client.get_repo_by_id(repoId)).json()
        
        return self.__repomgr_config

    async def __get_repourl_from_repomgr_config(self):
        cfg = await self.__get_repomgr_config()
        
        if cfg is None:
            return ""
        else:
            return cfg['url']

    async def __get_primary_branch_from_repomgr_config(self):
        cfg = await self.__get_repomgr_config()
        
        if cfg is not None:
            if "branches" in cfg.keys():
                for b in cfg['branches']:
                    if "isDefaultBranch" in b.keys() and bool(b['isDefaultBranch']):
                        if "name" in b.keys():
                            return b['name']
        return ""


    async def __get_logical_repo_url(self):
        if len(await self.__get_repourl_from_repomgr_config()) > 0:
            return await self.__get_repourl_from_repomgr_config()
        elif len(self.__project_data['repoUrl']) > 0:
            return self.__project_data['repoUrl']
        elif len(await self.__get_repourl_from_undocumented_config()) > 0:
            return await self.__get_repourl_from_undocumented_config()
        else:
            return None

    async def __get_logical_primary_branch(self):
        if len(self.__project_data['mainBranch']) > 0:
            return self.__project_data['mainBranch']
        elif len(await self.__get_primary_branch_from_repomgr_config()) > 0:
            return await self.__get_primary_branch_from_repomgr_config()

        return None
    
    async def __get_scm_config(self):
        if not await self.is_scm_imported:
            return None
        
        async with self.__lock:
            if not self.__fetched_scm_config:
                self.__fetched_scm_config = True
                self.__scm_config = (await self.__client.get_scm_by_id(await self.scm_id)).json()
        
        return self.__scm_config
        
    @property
    async def primary_branch(self):
        return await self.__get_logical_primary_branch()

    @property
    async def repo_url(self):
        url = await self.__get_logical_repo_url()
        return url if url is not None and len(url) > 0 else None
    
    @property
    async def is_scm_imported(self):
        return await self.__get_repomgr_config() is not None


    @property
    async def scm_id(self):
        if not await self.is_scm_imported:
            return None
        
        cfg = await self.__get_repomgr_config()

        if cfg is None:
            return None
        elif "scmId" in cfg.keys(): 
            return cfg['scmId']
        else:
            return None
        
    @property
    async def scm_org(self):
        if not await self.is_scm_imported:
            return None

        return CloneUrlParser(await self.scm_type, await self.repo_url).org
        

    @property
    async def scm_type(self):
        if not await self.is_scm_imported:
            return None

        cfg = await self.__get_scm_config()
        if cfg is None:
            return None
        elif "type" in cfg.keys():
            return cfg['type']
        else:
            return None

    @property
    def project_id(self):
        return self.__project_data['id']
    
    async def get_enabled_scanners(self, by_branch):
        engines = []

        if await self.is_scm_imported:
            # Use the engine configuration on the import
            cfg = await self.__get_repomgr_config()

            for k in cfg.keys():
                if k.lower().endswith("scannerenabled") and bool(cfg[k]):
                    engines.append(k.lower().removesuffix("scannerenabled"))

        if len(engines) == 0:
            # If no engines configured by the import config, use the engines for the last scan.
            last_scan = (await self.__client.get_projects_last_scan(project_ids=[self.project_id], branch=by_branch, limit=1)).json()
            if len(last_scan) > 0:
                latest_scan_header = list(last_scan.values())[0]
                if 'engines' in latest_scan_header.keys():
                    engines = latest_scan_header['engines'] 

        return engines

