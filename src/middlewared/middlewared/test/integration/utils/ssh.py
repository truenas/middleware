import os
import sys

try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from auto_config import user as default_user, password as default_password, ip as default_ip
    from functions import SSH_TEST
except ImportError:
    default_user = None
    default_password = None
    default_ip = None

__all__ = ["ssh"]


def ssh(command, check=True, complete_response=False, *, user=default_user, password=default_password, ip=default_ip):
    result = SSH_TEST(command, user, password, ip)
    if check:
        assert result["result"] is True, f"stdout: {result['output']}\nstderr: {result['stderr']}"
    return result if complete_response else result["output"]
