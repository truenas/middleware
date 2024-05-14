import os
import sys

try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from auto_config import user as default_user, password as default_password
    from functions import SSH_TEST
except ImportError:
    default_user = None
    default_password = None

__all__ = ["ssh"]


def ssh(command, check=True, complete_response=False, *, user=default_user, password=default_password, ip=None):
    result = SSH_TEST(command, user, password, ip)
    if check:
        assert result["result"], result["output"]
    return result if complete_response else result["stdout"]
