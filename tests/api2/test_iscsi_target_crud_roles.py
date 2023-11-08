import errno

import pytest

from middlewared.client import ClientException
from middlewared.test.integration.assets.iscsi import iscsi_target
from middlewared.test.integration.assets.account import unprivileged_user_client


@pytest.fixture(scope="module")
def target():
    with iscsi_target({"name": "dummytarget1", "alias": "Just for rigging purposes"}) as result:
        yield result


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_TARGET_READ"])
def test_read_role_can_read(role):
    with unprivileged_user_client(roles=[role]) as c:
        c.call("iscsi.target.query")


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_TARGET_READ"])
def test_read_role_cant_write(target, role):
    with unprivileged_user_client(roles=[role]) as c:
        with pytest.raises(ClientException) as ve:
            c.call("iscsi.target.create", {
                "name": "test1",
            })
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.target.validate_name", "newname1")
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.target.update", target['id'], {})
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.target.delete", target['id'])
        assert ve.value.errno == errno.EACCES


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_ISCSI_TARGET_WRITE"])
def test_write_role_can_write(role):
    with unprivileged_user_client(roles=[role]) as c:
        # Just do a minimal create here (lower cost)
        item = c.call("iscsi.target.create", {
            "name": "test1",
        })
        try:
            c.call("iscsi.target.validate_name", "newname1")
            c.call("iscsi.target.update", item["id"], {})
        finally:
            c.call("iscsi.target.delete", item["id"])
