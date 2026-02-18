from utils import get_threads_config
from posix_ipc import Semaphore, O_CREX

# Init the scan thread semaphore
Semaphore(f"/cxone_scan", flags=O_CREX, initial_value=get_threads_config())
