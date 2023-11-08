import errno

import pytest

from middlewared.client import ClientException
from middlewared.test.integration.assets.iscsi import iscsi_auth
from middlewared.test.integration.assets.account import unprivileged_user_client


@pytest.fixture(scope="module")
def auth():
    with iscsi_auth({"tag": "42", "user": "dummyuser", "secret": "dummysecret1234"}) as result:
        yield result


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_AUTH_READ"])
def test_read_role_can_read(role):
    with unprivileged_user_client(roles=[role]) as c:
        c.call("iscsi.auth.query")


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_AUTH_READ"])
def test_read_role_cant_write(auth, role):
    with unprivileged_user_client(roles=[role]) as c:
        with pytest.raises(ClientException) as ve:
            c.call("iscsi.auth.create", {
                "tag": "1",
                "user": "someusername",
                "secret": "password1234",
            })
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.auth.update", auth['id'], {})
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.auth.delete", auth['id'])
        assert ve.value.errno == errno.EACCES


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_ISCSI_AUTH_WRITE"])
def test_write_role_can_write(role):
    with unprivileged_user_client(roles=[role]) as c:
        item = c.call("iscsi.auth.create", {
            "tag": "1",
            "user": "someusername",
            "secret": "password1234",
        })

        c.call("iscsi.auth.update", item["id"], {})

        c.call("iscsi.auth.delete", item["id"])
