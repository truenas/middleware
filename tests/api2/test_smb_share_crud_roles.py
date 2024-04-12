import errno

import pytest

from middlewared.client import ClientException
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call


@pytest.fixture(scope="module")
def ds():
    with dataset("smb_crud_test") as ds:
        yield ds


@pytest.fixture(scope="module")
def share():
    with dataset("smb_crud_test2") as ds:
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

        # READ access should allow reading ACL
        c.call("sharing.smb.getacl", {"share_name": share["name"]})

        with pytest.raises(ClientException) as ve:
            c.call("sharing.smb.setacl", {"share_name": share["name"]})
        assert ve.value.errno == errno.EACCES

        # Gathering session info should be more administrative-level op
        with pytest.raises(ClientException) as ve:
            c.call("smb.status")
        assert ve.value.errno == errno.EACCES


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_SMB_WRITE"])
def test_write_role_can_write(ds, role):
    with unprivileged_user_client(roles=[role]) as c:
        share = c.call("sharing.smb.create", {"path": f"/mnt/{ds}", "name": "test"})

        c.call("sharing.smb.update", share["id"], {})

        # READ access should allow reading ACL
        c.call("sharing.smb.getacl", {"share_name": share["name"]})
        c.call("sharing.smb.setacl", {"share_name": share["name"]})
        c.call("sharing.smb.delete", share["id"])
        c.call("smb.status")

        c.call("service.start", "cifs")
        c.call("service.restart", "cifs")
        c.call("service.reload", "cifs")
        c.call("service.stop", "cifs")


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_SMB_WRITE"])
def test_auxsmbconf_rejected_create(ds, role):
    share = None
    with unprivileged_user_client(roles=[role]) as c:
        with pytest.raises(ValidationErrors) as ve:
            try:
                share = c.call('sharing.smb.create', {
                    'name': 'FAIL',
                    'path': f'/mnt/{ds}',
                    'auxsmbconf': 'test:param = CANARY'
                })
            finally:
                if share:
                    call('sharing.smb.delete', share['id'])


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_SMB_WRITE"])
def test_auxsmbconf_rejected_update(ds, role):
    with smb_share(f'/mnt/{ds}', 'FAIL') as share:
        with unprivileged_user_client(roles=[role]) as c:
            with pytest.raises(ValidationErrors):
                c.call('sharing.smb.update', share['id'], {'auxsmbconf': 'test:param = Bob'})
