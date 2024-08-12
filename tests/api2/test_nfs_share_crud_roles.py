import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_NFS_READ"])
def test_read_role_can_read(unprivileged_user_fixture, role):
    common_checks(unprivileged_user_fixture, "sharing.nfs.query", role, True, valid_role_exception=False)
    common_checks(unprivileged_user_fixture, "nfs.client_count", role, True, valid_role_exception=False)


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_NFS_READ"])
def test_read_role_cant_write(unprivileged_user_fixture, role):
    common_checks(unprivileged_user_fixture, "sharing.nfs.create", role, False)
    common_checks(unprivileged_user_fixture, "sharing.nfs.update", role, False)
    common_checks(unprivileged_user_fixture, "sharing.nfs.delete", role, False)
    common_checks(unprivileged_user_fixture, "nfs.get_nfs3_clients", role, False)
    common_checks(unprivileged_user_fixture, "nfs.get_nfs4_clients", role, False)


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_NFS_WRITE"])
def test_write_role_can_write(unprivileged_user_fixture, role):
    common_checks(unprivileged_user_fixture, "sharing.nfs.create", role, True)
    common_checks(unprivileged_user_fixture, "sharing.nfs.update", role, True)
    common_checks(unprivileged_user_fixture, "sharing.nfs.delete", role, True)
    common_checks(unprivileged_user_fixture, "nfs.get_nfs3_clients", role, True, valid_role_exception=False)
    common_checks(unprivileged_user_fixture, "nfs.get_nfs4_clients", role, True, valid_role_exception=False)
    common_checks(
        unprivileged_user_fixture, "service.start", role, True, method_args=["nfs"], valid_role_exception=False
    )
    common_checks(
        unprivileged_user_fixture, "service.restart", role, True, method_args=["nfs"], valid_role_exception=False
    )
    common_checks(
        unprivileged_user_fixture, "service.reload", role, True, method_args=["nfs"], valid_role_exception=False
    )
    common_checks(
        unprivileged_user_fixture, "service.stop", role, True, method_args=["nfs"], valid_role_exception=False
    )
