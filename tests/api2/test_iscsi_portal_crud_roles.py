import errno

import pytest

from middlewared.client import ClientException
from middlewared.test.integration.assets.iscsi import iscsi_portal
from middlewared.test.integration.assets.account import unprivileged_user_client


@pytest.fixture(scope="module")
def portal():
    with iscsi_portal({"listen": [{"ip": "::"}], "comment": "IPv6"}) as result:
        yield result


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_PORTAL_READ"])
def test_read_role_can_read(role):
    with unprivileged_user_client(roles=[role]) as c:
        c.call("iscsi.portal.query")


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_PORTAL_READ"])
def test_read_role_cant_write(portal, role):
    with unprivileged_user_client(roles=[role]) as c:
        with pytest.raises(ClientException) as ve:
            c.call("iscsi.portal.create", {
                "listen": [{"ip": "0.0.0.0"}],
                "comment": "IPv4",
            })
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.portal.update", portal['id'], {})
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.portal.delete", portal['id'])
        assert ve.value.errno == errno.EACCES


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_ISCSI_PORTAL_WRITE"])
def test_write_role_can_write(role):
    with unprivileged_user_client(roles=[role]) as c:
        item = c.call("iscsi.portal.create", {
            "listen": [{"ip": "0.0.0.0"}],
            "comment": "IPv4",
        })
        try:
            c.call("iscsi.portal.update", item["id"], {})
        finally:
            c.call("iscsi.portal.delete", item["id"])
