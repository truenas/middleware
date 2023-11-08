import errno

import pytest

from middlewared.client import ClientException
from middlewared.test.integration.assets.iscsi import iscsi_extent, iscsi_target
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.account import unprivileged_user_client


@pytest.fixture(scope="module")
def ds():
    with dataset("test", {"type": "VOLUME", "volsize": 1048576}) as ds:
        yield ds


@pytest.fixture(scope="module")
def share():
    with dataset("test2", {"type": "VOLUME", "volsize": 1048576}) as ds:
        with iscsi_extent({
            "name": "test_extent",
            "type": "DISK",
            "disk": f"zvol/{ds}",
        }) as share:
            yield share


@pytest.fixture(scope="module")
def target():
    with iscsi_target({"name": "test1", "alias": "Target to test targetextent"}) as result:
        yield result


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_READ", "SHARING_ISCSI_TARGETEXTENT_READ"])
def test_read_role_can_read(role):
    with unprivileged_user_client(roles=[role]) as c:
        c.call("iscsi.targetextent.query")


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_READ", "SHARING_ISCSI_TARGETEXTENT_READ"])
def test_read_role_cant_write(ds, share, target, role):
    with unprivileged_user_client(roles=[role]) as c:
        with pytest.raises(ClientException) as ve:
            c.call("iscsi.targetextent.create", {
                "target": target["id"],
                "lunid": 0,
                "extent": share["id"],
            })
        assert ve.value.errno == errno.EACCES

        dummyID = 0x845fed
        with pytest.raises(ClientException) as ve:
            c.call("iscsi.targetextent.update", dummyID, {})
        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            c.call("iscsi.targetextent.delete", dummyID)
        assert ve.value.errno == errno.EACCES


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_ISCSI_WRITE", "SHARING_ISCSI_TARGETEXTENT_WRITE"])
def test_write_role_can_write(ds, share, target, role):
    with unprivileged_user_client(roles=[role]) as c:
        item = c.call("iscsi.targetextent.create", {
            "target": target["id"],
            "lunid": 0,
            "extent": share["id"],
        })
        try:
            c.call("iscsi.targetextent.update", item["id"], {})
        finally:
            c.call("iscsi.targetextent.delete", item["id"])
