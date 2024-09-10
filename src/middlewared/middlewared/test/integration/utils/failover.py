import contextlib
import os
import sys

try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from auto_config import ha, hostname
except ImportError:
    ha = False
    hostname = None

from .call import call

__all__ = ["disable_failover"]


@contextlib.contextmanager
def disable_failover():
    if ha:
        call("failover.update", {"disabled": True, "master": True})

    try:
        yield
    finally:
        if ha:
            call("failover.update", {"disabled": False, "master": True})
