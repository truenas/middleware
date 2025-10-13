import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.roles import common_checks
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call


@pytest.fixture(scope='module')
def create_dataset():
    with dataset('smb_roles_test') as ds:
        yield ds


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_SMB_READ"])
def test_read_role_can_read(unprivileged_user_fixture, role):
    common_checks(unprivileged_user_fixture, "sharing.smb.query", role, True, valid_role_exception=False)


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_SMB_READ"])
def test_read_role_cant_write(unprivileged_user_fixture, role):
    common_checks(unprivileged_user_fixture, "sharing.smb.create", role, False)
    common_checks(unprivileged_user_fixture, "sharing.smb.update", role, False)
    common_checks(unprivileged_user_fixture, "sharing.smb.delete", role, False)

    common_checks(unprivileged_user_fixture, "sharing.smb.getacl", role, True)
    common_checks(unprivileged_user_fixture, "sharing.smb.setacl", role, False)
    # common_checks(unprivileged_user_fixture, "smb.status", role, False)


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_SMB_WRITE"])
def test_write_role_can_write(unprivileged_user_fixture, role):
    common_checks(unprivileged_user_fixture, "sharing.smb.create", role, True)
    common_checks(unprivileged_user_fixture, "sharing.smb.update", role, True)
    common_checks(unprivileged_user_fixture, "sharing.smb.delete", role, True)

    common_checks(unprivileged_user_fixture, "sharing.smb.getacl", role, True)
    common_checks(unprivileged_user_fixture, "sharing.smb.setacl", role, True)
    # common_checks(unprivileged_user_fixture, "smb.status", role, True, valid_role_exception=False)

    common_checks(
        unprivileged_user_fixture, "service.control", role, True, method_args=["START", "cifs"],
        method_kwargs=dict(job=True), valid_role_exception=False,
    )
    common_checks(
        unprivileged_user_fixture, "service.control", role, True, method_args=["RESTART", "cifs"],
        method_kwargs=dict(job=True), valid_role_exception=False,
    )
    common_checks(
        unprivileged_user_fixture, "service.control", role, True, method_args=["RELOAD", "cifs"],
        method_kwargs=dict(job=True), valid_role_exception=False,
    )
    common_checks(
        unprivileged_user_fixture, "service.control", role, True, method_args=["STOP", "cifs"],
        method_kwargs=dict(job=True), valid_role_exception=False,
    )


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_SMB_WRITE"])
def test_auxsmbconf_rejected_create(create_dataset, role):
    share = None
    with unprivileged_user_client(roles=[role]) as c:
        with pytest.raises(ValidationErrors) as ve:
            try:
                share = c.call('sharing.smb.create', {
                    'name': 'FAIL',
                    'path': f'/mnt/{create_dataset}',
                    'auxsmbconf': 'test:param = CANARY'
                })
            finally:
                if share:
                    call('sharing.smb.delete', share['id'])


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_SMB_WRITE"])
def test_auxsmbconf_rejected_update(create_dataset, role):
    with smb_share(f'/mnt/{create_dataset}', 'FAIL') as share:
        with unprivileged_user_client(roles=[role]) as c:
            with pytest.raises(ValidationErrors):
                c.call('sharing.smb.update', share['id'], {'auxsmbconf': 'test:param = Bob'})
