from .projects import ProjectRepoConfig
from . import CxOneClient


class ScanInvoker:
    pass

    @staticmethod
    async def scan(cxone_client : CxOneClient, project_id : str, branch : str, engines : list = None , tags : dict = None, src_zip_path : str = None) -> str:
        pass