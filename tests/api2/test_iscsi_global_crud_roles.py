import errno

import pytest

from middlewared.client import ClientException
from middlewared.test.integration.assets.account import unprivileged_user_client


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_GLOBAL_READ"])
def test_read_role_can_read(role):
    with unprivileged_user_client(roles=[role]) as c:
        c.call("iscsi.global.config")
        c.call("iscsi.global.sessions")
        c.call("iscsi.global.client_count")
        c.call("iscsi.global.alua_enabled")


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_GLOBAL_READ"])
def test_read_role_cant_write(role):
    with unprivileged_user_client(roles=[role]) as c:
        with pytest.raises(ClientException) as ve:
            c.call("iscsi.global.update", {})
        assert ve.value.errno == errno.EACCES


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_ISCSI_GLOBAL_WRITE"])
def test_write_role_can_write(role):
    with unprivileged_user_client(roles=[role]) as c:
        c.call("iscsi.global.update", {})
