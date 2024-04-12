import asyncio, uuid, requests, urllib, datetime, re
from requests.compat import urljoin
from pathlib import Path

DEFAULT_SCHEME = "https"

class AuthException(BaseException):
    pass
    
class CommunicationException(BaseException):

    @staticmethod
    def __clean(content):
        if type(content) is list:
            return [CommunicationException.__clean(x) for x in content]
        elif type(content) is tuple:
            return (CommunicationException.__clean(x) for x in content)
        elif type(content) is dict:
            return {k:CommunicationException.__clean(v) for k,v in content.items()}
        elif type(content) is str:
            if re.match("^Bearer.*", content):
                return "REDACTED"
            else:
                return content
        else:
            return content

    def __init__(self, op, *args, **kwargs):
        BaseException.__init__(self, f"Operation: {op.__name__} args: [{CommunicationException.__clean(args)}] kwargs: [{CommunicationException.__clean(kwargs)}]")


class CxOneAuthEndpoint:

    __AUTH_PREFIX = "/auth/realms"
    __AUTH_SUFFIX = "protocol/openid-connect/token"
    
    __ADMIN_PREFIX = "/auth/admin/realms"

    def __init__(self, tenant_name, server, scheme=DEFAULT_SCHEME):
        self.__endpoint_url = urllib.parse.urlunsplit((scheme, server, f"{CxOneAuthEndpoint.__AUTH_PREFIX}/{tenant_name}/{CxOneAuthEndpoint.__AUTH_SUFFIX}", None, None))
        self.__admin_endpoint_url = urllib.parse.urlunsplit((scheme, server, f"{CxOneAuthEndpoint.__ADMIN_PREFIX}/{tenant_name}/", None, None))

    @property
    def admin_endpoint(self):
        return self.__admin_endpoint_url

    def __str__(self):
        return str(self.__endpoint_url)


class AuthUS(CxOneAuthEndpoint):
    def __init__(self, tenant_name):
        super().__init__(tenant_name, "iam.checkmarx.net")

class AuthUS2(CxOneAuthEndpoint):
    def __init__(self, tenant_name):
        super().__init__(tenant_name, "us.iam.checkmarx.net")

class AuthEU(CxOneAuthEndpoint):
    def __init__(self, tenant_name):
        super().__init__(tenant_name, "eu.iam.checkmarx.net")

class AuthANZ(CxOneAuthEndpoint):
    def __init__(self, tenant_name):
        super().__init__(tenant_name, "anz.iam.checkmarx.net")

class AuthIndia(CxOneAuthEndpoint):
    def __init__(self, tenant_name):
        super().__init__(tenant_name, "ind.iam.checkmarx.net")

class AuthSingapore(CxOneAuthEndpoint):
    def __init__(self, tenant_name):
        super().__init__(tenant_name, "sng.iam.checkmarx.net")


AuthRegionEndpoints = {
    "US" : AuthUS,
    "US2" : AuthUS2,
    "EU" : AuthEU,
    "EU2" : AuthEU,
    "ANZ" : AuthANZ,
    "India" : AuthIndia,
    "Singapore" : AuthSingapore
}


class CxOneApiEndpoint:
    def __init__(self, server, scheme=DEFAULT_SCHEME):
        self.__endpoint_url = urllib.parse.urlunsplit((scheme, server, "/api/", None, None))

    def __str__(self):
        return str(self.__endpoint_url)

class ApiUS(CxOneApiEndpoint):
    def __init__(self):
        super().__init__("ast.checkmarx.net")

class ApiUS2(CxOneApiEndpoint):
    def __init__(self):
        super().__init__("us.ast.checkmarx.net")

class ApiEU(CxOneApiEndpoint):
    def __init__(self):
        super().__init__("eu.ast.checkmarx.net")

class ApiEU2(CxOneApiEndpoint):
    def __init__(self):
        super().__init__("eu-2ast.checkmarx.net")

class ApiANZ(CxOneApiEndpoint):
    def __init__(self):
        super().__init__("anz.ast.checkmarx.net")

class ApiIndia(CxOneApiEndpoint):
    def __init__(self):
        super().__init__("ind.ast.checkmarx.net")

class ApiSingapore(CxOneApiEndpoint):
    def __init__(self):
        super().__init__("sng.ast.checkmarx.net")


ApiRegionEndpoints = {
    "US" : ApiUS,
    "US2" : ApiUS2,
    "EU" : ApiEU,
    "EU2" : ApiEU2,
    "ANZ" : ApiANZ,
    "India" : ApiIndia,
    "Singapore" : ApiSingapore
}


# A utility decorator to convert kwargs used for API calls
# to their proper name when the API defines them with "-"
# in the argument name.  This allows API methods to use kwargs
# with names defined in the API rather than mapping argument names
# to API query parameters.
def dashargs(*args):

    def normalized_string(s):
        return s.replace('-', '').replace('_', '')


    def decorator(wrapped):
        async def wrapper(*inner_args, **inner_kwargs):

            normalized = {}

            for val in args:
                normalized[normalized_string(val)] = val


            to_delete = []
            to_add = {}

            for k in inner_kwargs:
                
                nk = normalized_string(k)

                if nk in normalized.keys():
                    to_add[normalized[nk]] = inner_kwargs[k]
                    to_delete.append(k)

            inner_kwargs = inner_kwargs | to_add

            for k in to_delete:
                del inner_kwargs[k]

            return await wrapped(*inner_args, **inner_kwargs)
        return wrapper
    return decorator


async def paged_api(coro, array_element, offset_field='offset', **kwargs):
    offset = 0
    buf = []

    while True:
        if len(buf) == 0:
            kwargs[offset_field] = offset
            buf = (await coro(**kwargs)).json()[array_element]
            
            if buf is None or len(buf) == 0:
                return
            
            offset = offset + len(buf)

        yield buf.pop()


class CxOneClient:
    __AGENT_NAME = 'CxOne PyClient'


    def __common__init(self, agent_name, agent_version, tenant_auth_endpoint, api_endpoint, timeout, retries, proxy, ssl_verify):
        with open(Path(__file__).parent / "version.txt", "rt") as version:
            self.__version = version.readline().rstrip()

        self.__agent = f"{agent_name}/{agent_version}/({CxOneClient.__AGENT_NAME}/{self.__version})"
        self.__proxy = proxy
        self.__ssl_verify = ssl_verify
        self.__auth_lock = asyncio.Lock()
        self.__corelation_id = str(uuid.uuid4())

        self.__auth_endpoint = tenant_auth_endpoint
        self.__api_endpoint = api_endpoint
        self.__timeout = timeout
        self.__retries = retries

        self.__auth_endpoint = tenant_auth_endpoint
        self.__api_endpoint = api_endpoint
        self.__timeout = timeout
        self.__retries = retries

        self.__auth_result = None





    @staticmethod
    def create_with_oauth(oauth_id, oauth_secret, agent_name, agent_version, tenant_auth_endpoint, api_endpoint, timeout=60, retries=3, proxy=None, ssl_verify=True):
        inst = CxOneClient()
        inst.__common__init(agent_name, agent_version, tenant_auth_endpoint, api_endpoint, timeout, retries, proxy, ssl_verify)

        inst.__auth_content = urllib.parse.urlencode( {
            "grant_type" : "client_credentials",
            "client_id" : oauth_id,
            "client_secret" : oauth_secret
        })

        return inst

    @staticmethod
    def create_with_api_key(api_key, agent_name, agent_version, tenant_auth_endpoint, api_endpoint, timeout=60, retries=3, proxy=None, ssl_verify=True):
        inst = CxOneClient()
        inst.__common__init(agent_name, agent_version, tenant_auth_endpoint, api_endpoint, timeout, retries, proxy, ssl_verify)

        inst.__auth_content = urllib.parse.urlencode( {
            "grant_type" : "refresh_token",
            "client_id" : "ast-app",
            "refresh_token" : api_key
        })

        return inst

    @property
    def auth_endpoint(self):
        return str(self.__auth_endpoint)
    
    @property
    def api_endpoint(self):
        return str(self.__api_endpoint)
    
    @property
    def admin_endpoint(self):
        return self.__auth_endpoint.admin_endpoint

    async def __get_request_headers(self):
        if self.__auth_result is None:
            await self.__do_auth()

        return {
            "Authorization" : f"Bearer {self.__auth_result['access_token']}",
            "Accept" : "*/*; version=1.0", 
            "User-Agent" : self.__agent,
            "CorrelationId" : self.__corelation_id
            }

    async def __auth_task(self):
        response = None
        for _ in range(0, self.__retries):
            response = await asyncio.to_thread(requests.post, self.auth_endpoint, data=self.__auth_content, timeout=self.__timeout, 
              proxies=self.__proxy, verify=self.__ssl_verify, headers={
                  "Content-Type" : "application/x-www-form-urlencoded",
                  "Accept" : "application/json"
              })
            if response.ok:
                return response.json()
        
        raise AuthException(response.reason if not response is None else "Unknown error")

    async def __do_auth(self):
        skip = False

        if self.__auth_lock.locked():
            skip = True
            async with self.__auth_lock:
                pass

        if not skip:
            async with self.__auth_lock:
                self.__auth_result = await self.__auth_task()
    
    async def __exec_request(self, op, *args, **kwargs):
        if not self.__proxy is None:
            kwargs['proxies'] = self.__proxy
        
        kwargs['verify'] = self.__ssl_verify

        for _ in range(0, self.__retries):
            auth_headers = await self.__get_request_headers()

            if 'headers' in kwargs.keys():
                for h in auth_headers.keys():
                    kwargs['headers'][h] = auth_headers[h]
            else:
                kwargs['headers'] = auth_headers
            
            response = await asyncio.to_thread(op, *args, **kwargs)

            if response.status_code == 401:
                await self.__do_auth()
            else:
                return response

        raise CommunicationException(op, *args, **kwargs)


    @staticmethod
    def __join_query_dict(url, querydict):
        query = []
        for key in querydict.keys():
            if querydict[key] is None:
                continue

            if isinstance(querydict[key], list):
                query.append(f"{urllib.parse.quote(key)}={urllib.parse.quote(','.join(querydict[key]))}")
            elif isinstance(querydict[key], str):
                query.append(f"{urllib.parse.quote(key)}={urllib.parse.quote(querydict[key])}")
            elif isinstance(querydict[key], type(datetime)):
                pass # TODO: datetime as ISO 8601 string
            else:
                query.append(f"{urllib.parse.quote(key)}={querydict[key]}")


        return urljoin(url, f"?{'&'.join(query)}" if len(query) > 0 else '')

    @dashargs("tags-keys", "tags-values")
    async def get_applications(self, **kwargs):
        url = urljoin(self.api_endpoint, "applications")
        url = CxOneClient.__join_query_dict(url, kwargs)
        return await self.__exec_request(requests.get, url)

    async def get_application(self, id, **kwargs):
        url = urljoin(self.api_endpoint, f"applications/{id}")
        url = CxOneClient.__join_query_dict(url, kwargs)
        return await self.__exec_request(requests.get, url)

    @dashargs("repo-url", "name-regex", "tags-keys", "tags-values")
    async def get_projects(self, **kwargs):
        url = urljoin(self.api_endpoint, "projects")
        url = CxOneClient.__join_query_dict(url, kwargs)
        return await self.__exec_request(requests.get, url)


    async def get_project(self, projectid):
        url = urljoin(self.api_endpoint, f"projects/{projectid}")
        return await self.__exec_request(requests.get, url)

    async def get_project_configuration(self, projectid):
        url = urljoin(self.api_endpoint, f"configuration/project?project-id={projectid}")
        return await self.__exec_request(requests.get, url)

    async def get_tenant_configuration(self):
        url = urljoin(self.api_endpoint, f"configuration/tenant")
        return await self.__exec_request(requests.get, url)

    @dashargs("from-date", "project-id", "project-ids", "scan-ids", "project-names", "source-origin", "source-type", "tags-keys", "tags-values", "to-date")
    async def get_scans(self, **kwargs):
        url = urljoin(self.api_endpoint, "scans")
        url = CxOneClient.__join_query_dict(url, kwargs)
        return await self.__exec_request(requests.get, url)
    
    @dashargs("scan-ids")
    async def get_sast_scans_metadata(self, **kwargs):
        url = urljoin(self.api_endpoint, "sast-metadata")
        url = CxOneClient.__join_query_dict(url, kwargs)
        return await self.__exec_request(requests.get, url)

    async def get_sast_scan_metadata(self, scanid, **kwargs):
        url = urljoin(self.api_endpoint, f"sast-metadata/{scanid}")
        url = CxOneClient.__join_query_dict(url, kwargs)
        return await self.__exec_request(requests.get, url)

    @dashargs("source-node-operation", "source-node", "source-line-operation", "source-line", "source-file-operation", "source-file", \
              "sink-node-operation", "sink-node", "sink-line-operation", "sink-line", "sink-file-operation", \
                "sink-file", "result-ids", "preset-id", "number-of-nodes-operation", "number-of-nodes", "notes-operation", \
                    "first-found-at-operation", "first-found-at", "apply-predicates")
    async def get_sast_scan_aggregate_results(self, scanid, groupby_field=['SEVERITY'], **kwargs):
        url = urljoin(self.api_endpoint, f"sast-scan-summary/aggregate")
        url = CxOneClient.__join_query_dict(url, kwargs | { 
            'scan-id' : scanid,
            'group-by-field' : groupby_field
        })
        return await self.__exec_request(requests.get, url)

    async def execute_scan(self, payload, **kwargs):
        url = urljoin(self.api_endpoint, "scans")
        url = CxOneClient.__join_query_dict(url, kwargs)
        return await self.__exec_request(requests.post, url, json=payload)

    async def get_sast_scan_log(self, scanid, stream=False):
        url = urljoin(self.api_endpoint, f"logs/{scanid}/sast")
        response = await self.__exec_request(requests.get, url)

        if response.ok and response.status_code == 307:
            response = await self.__exec_request(requests.get, response.headers['Location'], stream=stream)

        return response

    async def get_groups(self, **kwargs):
        url = CxOneClient.__join_query_dict(urljoin(self.admin_endpoint, "groups"), kwargs)
        return await self.__exec_request(requests.get, url)

    async def get_groups(self, **kwargs):
        url = CxOneClient.__join_query_dict(urljoin(self.admin_endpoint, "groups"), kwargs)
        return await self.__exec_request(requests.get, url)

    async def get_scan_workflow(self, scanid, **kwargs):
        url = urljoin(self.api_endpoint, f"scans/{scanid}/workflow")
        url = CxOneClient.__join_query_dict(url, kwargs)
        return await self.__exec_request(requests.get, url)

class ProjectRepoConfig:

    def __init__(self, cxone_client, project_data):
        self.__client = cxone_client
        self.__project_data = project_data
        self.__fetched_undocumented_config = False
        self.__lock = asyncio.Lock()
   
    async def __get_logical_repo_url(self):
        # The documented project API seems to have a bug and does not return the repoUrl.  The undocumented
        # API used by the UI has it.  The undocumented API will no longer be called when the project
        # API is fixed.
        async with self.__lock:
            if len(self.__project_data['repoUrl']) == 0 and not self.__fetched_undocumented_config:
                self.__fetched_undocumented_config = True
                config = (await self.__client.get_project_configuration(self.__project_data['id'])).json()

                for entry in config:
                    if entry['key'] == "scan.handler.git.repository":
                        self.__project_data['repoUrl'] = entry['value']
            
            return self.__project_data['repoUrl']

    @property
    async def primary_branch(self):
        return self.__project_data['mainBranch'] if len(self.__project_data['mainBranch']) > 0 else None

    @property
    async def repo_url(self):
        url = await self.__get_logical_repo_url()
        return url if len(url) > 0 else None