import errno

import pytest

from middlewared.client import ClientException
from middlewared.test.integration.assets.iscsi import iscsi_extent
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.account import unprivileged_user_client


@pytest.fixture(scope="session")
def ds():
    with dataset("test", {"type": "VOLUME", "volsize": 1048576}) as ds:
        yield ds


@pytest.fixture(scope="session")
def share():
    with dataset("test2", {"type": "VOLUME", "volsize": 1048576}) as ds:
        with iscsi_extent({
            "name": "test_extent",
            "type": "DISK",
            "disk": f"zvol/{ds}",
        }) as share:
            yield share


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_EXTENT_READ"])
def test_read_role_can_read(role):
    with unprivileged_user_client(roles=[role]) as c:
        c.call("iscsi.extent.query")


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_EXTENT_READ"])
def test_read_role_cant_write(ds, share, role):
    with unprivileged_user_client(roles=[role]) as c:
        with pytest.raises(ClientException) as ve:
            c.call("iscsi.extent.create", {
                "name": "test_extent",
                "type": "DISK",
                "disk": f"zvol/{ds}",
            })
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.extent.update", share["id"], {})
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.extent.delete", share["id"])
        assert ve.value.errno == errno.EACCES


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_ISCSI_EXTENT_WRITE"])
def test_write_role_can_write(ds, role):
    with unprivileged_user_client(roles=[role]) as c:
        share = c.call("iscsi.extent.create", {
            "name": "test_extent_2",
            "type": "DISK",
            "disk": f"zvol/{ds}",
        })

        c.call("iscsi.extent.update", share["id"], {})

        c.call("iscsi.extent.delete", share["id"])
