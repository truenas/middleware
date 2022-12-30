import os
import sys

try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from auto_config import user, password, ip
    from functions import SSH_TEST
except ImportError:
    pass

__all__ = ["ssh"]


def ssh(command, check=True, complete_response=False, _ip=None):
    _ip = _ip if _ip is not None else ip
    result = SSH_TEST(command, user, password, ip)
    if check:
        assert result["result"] is True, f"stdout: {result['output']}\nstderr: {result['stderr']}"
    return result if complete_response else result["output"]
