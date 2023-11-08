import errno

import pytest

from middlewared.client import ClientException
from middlewared.test.integration.assets.iscsi import iscsi_host
from middlewared.test.integration.assets.account import unprivileged_user_client


@pytest.fixture(scope="module")
def host():
    with iscsi_host({"ip": "1.1.2.8", "description": "Target to test targetextent"}) as result:
        yield result


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_HOST_READ"])
def test_read_role_can_read(host, role):
    with unprivileged_user_client(roles=[role]) as c:
        c.call("iscsi.host.query")
        c.call("iscsi.host.get_initiators", host["id"])
        c.call("iscsi.host.get_targets", host["id"])


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_HOST_READ"])
def test_read_role_cant_write(host, role):
    with unprivileged_user_client(roles=[role]) as c:
        with pytest.raises(ClientException) as ve:
            c.call("iscsi.host.create", {
                "ip": "1.2.3.4",
                "description": "test host for CRUD role",
            })
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.host.update", host["id"], {})
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.host.set_initiators", host["id"], [])
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.host.delete", host["id"])
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.host.set_initiators", host["id"], [])
        assert ve.value.errno == errno.EACCES


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_ISCSI_HOST_WRITE"])
def test_write_role_can_write(role):
    with unprivileged_user_client(roles=[role]) as c:
        item = c.call("iscsi.host.create", {
            "ip": "1.2.3.4",
            "description": "test host for CRUD role",
        })
        try:
            c.call("iscsi.host.update", item["id"], {})
            c.call("iscsi.host.set_initiators", item["id"], [])
            c.call("iscsi.host.set_targets", item["id"], [])
        finally:
            c.call("iscsi.host.delete", item["id"])
