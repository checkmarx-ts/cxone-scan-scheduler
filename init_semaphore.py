from utils import get_threads_config
from posix_ipc import Semaphore, O_CREAT

# Init the scan thread semaphore
Semaphore(f"/cxone_scan", flags=O_CREAT, initial_value=get_threads_config())
