import pytest

from middlewared.apps.webshell_app import _shell_home_and_cwd
from middlewared.utils.auth import ShellAppType

USER_HOME = "/mnt/tank/alice"

EXPECTED = {
    ShellAppType.HOST: (USER_HOME, "/root"),
    ShellAppType.VM: ("/root", "/root"),
    ShellAppType.CONTAINER: ("/root", "/root"),
    ShellAppType.APP: ("/root", "/root"),
}


@pytest.mark.parametrize("shell_type", list(ShellAppType))
def test_shell_home_and_cwd(shell_type):
    assert set(EXPECTED) == set(ShellAppType)
    assert _shell_home_and_cwd(shell_type, USER_HOME) == EXPECTED[shell_type]
