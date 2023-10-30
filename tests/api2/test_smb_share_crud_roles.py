import errno

import pytest

from middlewared.client import ClientException
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.account import unprivileged_user_client


@pytest.fixture(scope="session")
def ds():
    with dataset("test") as ds:
        yield ds


@pytest.fixture(scope="session")
def share():
    with dataset("test2") as ds:
        with smb_share(f"/mnt/{ds}", "test2") as share:
            yield share


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_SMB_READ"])
def test_read_role_can_read(role):
    with unprivileged_user_client(roles=[role]) as c:
        c.call("sharing.smb.query")


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_SMB_READ"])
def test_read_role_cant_write(ds, share, role):
    with unprivileged_user_client(roles=[role]) as c:
        with pytest.raises(ClientException) as ve:
            c.call("sharing.smb.create", {"path": f"/mnt/{ds}"})
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("sharing.smb.update", share["id"], {})
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("sharing.smb.delete", share["id"])
        assert ve.value.errno == errno.EACCES


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_SMB_WRITE"])
def test_write_role_can_write(ds, role):
    with unprivileged_user_client(roles=[role]) as c:
        share = c.call("sharing.smb.create", {"path": f"/mnt/{ds}", "name": "test"})

        c.call("sharing.smb.update", share["id"], {})

        c.call("sharing.smb.delete", share["id"])
