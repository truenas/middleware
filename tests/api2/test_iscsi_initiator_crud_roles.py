import errno

import pytest

from middlewared.client import ClientException
from middlewared.test.integration.assets.iscsi import iscsi_initiator
from middlewared.test.integration.assets.account import unprivileged_user_client


@pytest.fixture(scope="module")
def initiator():
    with iscsi_initiator({"initiators": ["host1", "host2"], "comment": "Dummy entry"}) as result:
        yield result


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_READ", "SHARING_ISCSI_INITIATOR_READ"])
def test_read_role_can_read(role):
    with unprivileged_user_client(roles=[role]) as c:
        c.call("iscsi.initiator.query")


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_READ", "SHARING_ISCSI_INITIATOR_READ"])
def test_read_role_cant_write(initiator, role):
    with unprivileged_user_client(roles=[role]) as c:
        with pytest.raises(ClientException) as ve:
            c.call("iscsi.initiator.create", {
                "initiators": ["hostnameAAA", "hostnameBBB"],
                "comment": "Not going to work",
            })
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.auth.update", initiator['id'], {})
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.auth.delete", initiator['id'])
        assert ve.value.errno == errno.EACCES


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_ISCSI_WRITE", "SHARING_ISCSI_INITIATOR_WRITE"])
def test_write_role_can_write(role):
    with unprivileged_user_client(roles=[role]) as c:
        item = c.call("iscsi.initiator.create", {
            "initiators": ["hostnameA", "hostnameB"],
            "comment": "Some very interesting comment",
        })
        try:
            c.call("iscsi.initiator.update", item["id"], {})
        finally:
            c.call("iscsi.initiator.delete", item["id"])
