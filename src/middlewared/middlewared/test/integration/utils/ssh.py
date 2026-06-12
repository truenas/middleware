from .client import password as _password
from .legacy_functions import SSH_TEST

__all__ = ["ssh"]


def ssh(command, check=True, complete_response=False, *,
        user=None, password=None, ip=None, timeout=120):
    user = user or "root"
    password = password or _password()

    result = SSH_TEST(command, user, password, ip, timeout=timeout)
    if check:
        assert result["result"], result["output"]
    return result if complete_response else result["stdout"]
