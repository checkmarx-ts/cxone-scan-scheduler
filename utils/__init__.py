import logging, hashlib, logging.config, glob
import os, re, logging, json
from pathlib import Path
from cron_validator import CronValidator
from pathlib import Path
from cxone_api import AuthRegionEndpoints, ApiRegionEndpoints, CxOneAuthEndpoint, CxOneApiEndpoint

def logger():
    return logging.getLogger("utils")

def get_log_level():
    return "INFO" if os.getenv('LOG_LEVEL') is None else os.getenv('LOG_LEVEL')


def load_logging_config_dict(filename):
    with open(filename, "rt") as cfg:
        config = json.load(cfg) 
        config['loggers']['root']['level'] = get_log_level()
        return config

def configure_normal_logging():
    logging.config.dictConfig(load_logging_config_dict("normal.json"))

def configure_audit_logging():
    logging.config.dictConfig(load_logging_config_dict("audit.json"))

def get_secret_path():
    tree = "run/secrets"
    default = f"/{tree}"

    if os.path.exists(default):
        return default
    elif os.path.exists(f"./{tree}"):
        return f"./{tree}"
    else:
        return "."

def load_secrets():
    path = get_secret_path()

    tenant = None
    with open(Path(path) / "cxone_tenant", "rt") as f:
        tenant = f.readline()

    oauth_id = None
    with open(Path(path) / "cxone_oauth_client_id", "rt") as f:
        oauth_id = f.readline()

    oauth_secret = None
    with open(Path(path) / "cxone_oauth_client_secret", "rt") as f:
        oauth_secret = f.readline()

    return (tenant, oauth_id, oauth_secret)

def load_schedule_update_delay():
    if not 'UPDATE_DELAY_SECONDS' in os.environ.keys():
        return 43200
    else:
        return int(os.environ['UPDATE_DELAY_SECONDS'])


def load_region():
    if not 'CXONE_REGION' in os.environ.keys():
        return None
    else:
        return os.environ['CXONE_REGION']


def load_endpoints(tenant_name):
    region = load_region()
    if region is not None:
        return AuthRegionEndpoints[region](tenant_name), ApiRegionEndpoints[region]()
    elif 'SINGLE_TENANT_AUTH' in os.environ.keys() and 'SINGLE_TENANT_API' in os.environ.keys():
        return CxOneAuthEndpoint(tenant_name, os.environ['SINGLE_TENANT_AUTH']), CxOneApiEndpoint(os.environ['SINGLE_TENANT_API']) 
    else:
        return None, None


def load_default_schedule():
    if 'DEFAULT_SCHEDULE' in os.environ.keys():
        return os.environ['DEFAULT_SCHEDULE']
    else:
        return None


def load_policies():
    policies = {}
    
    for k in os.environ.keys():
        if k.lower().startswith("policy_"):
            policy_name = k.lower()[len("policy_"):]
            policy_value = os.environ[k]
            if CronValidator.parse(policy_value) is None:
                logger().error(f"Crontab string [{policy_value}] for policy {policy_name} is invalid, skipping.")
                continue

            normalized_policy_name = policy_name.replace("_", "*").replace("-", "*")

            def insert_policy(name):
                if name not in policies.keys():
                    policies[name] = policy_value
                else:
                    logger().error(f"Policy [{name}] already exists, skipping duplicate definition")

            if normalized_policy_name == policy_name:
                insert_policy(normalized_policy_name)
            else:
                insert_policy(normalized_policy_name.replace("*", "-"))
                insert_policy(normalized_policy_name.replace("*", "_"))
    
    return policies


def make_safe_name(projectid, branch):
    return f"{projectid}_{hashlib.md5(branch.encode()).hexdigest()}"

def make_schedule_filename(index, projectid, branch):
    return f"{make_safe_name(projectid, branch)}_{index:04}"

def make_schedule_delete_fileglob(projectid):
    return f"{projectid}_*"

def write_cron_file(index, cron_schedule, projectid, branch, repo_url, engines, cron_path="/etc/cron.d"):
    engine_args = " ".join([f"-e {x}" for x in engines])
    filename = Path(cron_path) / make_schedule_filename(index, projectid, branch)
    log_out_string = "> /opt/cxone/logfifo 2>&1"
    cron_string = f"{cron_schedule} nobody cd /opt/cxone && ./scanner.py -p '{projectid}' -b '{branch}' -r '{repo_url}' -s '{cron_schedule}' {engine_args} {log_out_string}\n"

    with open(filename, "w") as cronfile:
        cronfile.write(cron_string)


def write_schedule(schedule):

    for scheds in schedule.values():
        index = 0
        for sched in scheds:
            write_cron_file(index, sched.schedule, sched.project_id, sched.branch, sched.repo_url, sched.engines)
            logger().debug(f"Writing schedule: {sched}")
            index = index + 1

def delete_scheduled_projects(schedule, cron_path="/etc/cron.d"):
    for proj_id in schedule.keys():
        for filename in glob.glob(str(Path(cron_path) / make_schedule_delete_fileglob(proj_id))):
            logger().debug(f"Removing cron file: {filename}")
            try:
                os.remove(filename)
            except FileNotFoundError as fnf:
                logger().exception(fnf)


class ScheduleString:

    __daily = "0 0 * * *"
    __hourly = "0 * * * *"

    def __init__(self, schedule, policy_dict):
        policy_strings = [f"^{x}$" for x in policy_dict.keys()]
        policy_strings.append("^hourly$|^daily$")
        self.__validator = re.compile("|".join(policy_strings))
        self.__schedule = schedule.lower().strip("\"\'")
        self.__policies = policy_dict

    def is_valid(self):
        try:
            return not self.__validator.search(self.__schedule) is None
        except ValueError:
            return False
    
    def get_crontab_schedule(self):
        if self.__schedule == "daily":
            return ScheduleString.__daily
        if self.__schedule == "hourly":
            return ScheduleString.__hourly
        else:
            return self.__policies[self.__schedule]
        
    def __repr__(self):
        return self.get_crontab_schedule()


class ProjectSchedule:

    def __init__(self, project_id, schedule_string, branch, engines, repo_url):
        self.__project_id = project_id
        self.__schedule = schedule_string
        self.__branch = branch
        self.__engines = engines
        self.__repo_url = repo_url

    @property
    def project_id(self):
        return self.__project_id
    
    @property
    def schedule(self):
        return str(self.__schedule)
    
    @property
    def branch(self):
        return self.__branch
    
    @property
    def engines(self):
        return self.__engines
    
    @property
    def repo_url(self):
        return self.__repo_url
    
    def __repr__(self):
        return f"{self.project_id}:{self.repo_url}:{self.branch}:{self.engines}:{self.schedule}"
    

class GroupSchedules:
    
    def __init__(self):
        self.__index = {}
        self.__log = logging.getLogger("GroupSchedules")


    def add_schedule(self, group, schedule):
        if group in self.__index.keys():
            self.__log.warning(f"Attempted to add duplicate schedule for group [{group}]")
            return

        if schedule.is_valid():
            self.__index[group] = schedule.get_crontab_schedule()
        else:
            self.__log.warning(f"Skipping invalid schedule [{schedule}] for group [{group}]")
    
    def get_schedule(self, group):
        if group in self.__index.keys():
            return self.__index[group]
        else:
            return None
        
    @property
    def empty(self):
        return len(self.__index.keys()) == 0
    
    def __repr__(self):
        return str(self.__index)


def load_group_schedules(policies):
    sched = GroupSchedules()

    group_keys = [x for x in os.environ.keys() if x.startswith("GROUP_")]

    schedule_keys = [f"SCHEDULE_{x[len('GROUP_'):]}" for x in group_keys if f"SCHEDULE_{x[len('GROUP_'):]}" in os.environ.keys()]

    for k in group_keys:
        lookup = k[len("GROUP_"):]
        schedkey = f"SCHEDULE_{lookup}"
        if schedkey in schedule_keys:
            ss = ScheduleString(os.environ[schedkey], policies)
            if ss.is_valid():
                sched.add_schedule(os.environ[k], ss)
            else:
                logger().error(f"{k} defines an invalid policy [{os.environ[schedkey]}], skipping.")

    return sched

def get_ssl_verify():
    if "SSL_VERIFY" in os.environ.keys():
        return False if os.environ['SSL_VERIFY'].lower() == 'false' else True
    else:
        return True

def get_proxy_config():
    if "PROXY" in os.environ.keys():
        proxy = os.environ['PROXY']
        return {"http" : proxy, "https" : proxy}
    else:
        return None

def available_engines():
    return ['sast', 'kics','sca','apisec']

def normalize_selected_engines_from_tag(engine_string):
    available = available_engines()
    result = available if 'all' in engine_string.lower() or len(engine_string) == 0 else []

    if len(result) == 0:
        requested = engine_string.lower().split(",")
        for eng in requested:
            if eng in available and not eng in result:
                result.append(eng)


    return result if len(result) > 0 else available

    
