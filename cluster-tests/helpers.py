import contextlib
from time import sleep
from concurrent.futures import ThreadPoolExecutor, as_completed
from protocols import SMB

from config import CLUSTER_IPS
from utils import make_request


def get_bool(parm):
    if isinstance(parm, bool):
        return parm

    if isinstance(parm, str):
        if parm.lower() == 'false':
            return False
        if parm.lower() == 'true':
            return True
        raise ValueError(parm)

    return bool(parm)


def ctdb_healthy(timeout=0):
    """
    In parallel, check if all nodes in the cluster are healthy. This will "wait"
    `timeout` seconds before giving up and returning.
    """
    if timeout > 60:
        timeout = 60  # limit to 60 for now
    sleep_timeout = 2

    with ThreadPoolExecutor() as exc:
        urls = [f'http://{ip}/api/v2.0/ctdb/general/healthy' for ip in CLUSTER_IPS]
        while True:
            futures = {exc.submit(make_request, 'get', url): url for url in urls}

            results = {}
            for fut in as_completed(futures):
                results[futures[fut]] = fut.result().json()

            rc = all(v is True for k, v in results.items())
            if timeout <= 0 or rc:
                # no timeout provided, expired timeout, or cluster is healthy
                return rc
            else:
                sleep(sleep_timeout)
                timeout -= sleep_timeout


@contextlib.contextmanager
def smb_connection(**kwargs):
    c = SMB()
    c.connect(**kwargs)

    try:
        yield c
    finally:
        c.disconnect()
