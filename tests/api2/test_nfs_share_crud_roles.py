import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_NFS_READ"])
def test_read_role_can_read(role):
    common_checks("sharing.nfs.query", role, True, valid_role_exception=False)
    common_checks("nfs.client_count", role, True, valid_role_exception=False)


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_NFS_READ"])
def test_read_role_cant_write(role):
    common_checks("sharing.nfs.create", role, False)
    common_checks("sharing.nfs.update", role, False)
    common_checks("sharing.nfs.delete", role, False)

    common_checks("nfs.get_nfs3_clients", role, False)
    common_checks("nfs.get_nfs4_clients", role, False)
    common_checks("nfs.add_principal", role, False)


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_NFS_WRITE"])
def test_write_role_can_write(role):
    common_checks("sharing.nfs.create", role, True)
    common_checks("sharing.nfs.update", role, True)
    common_checks("sharing.nfs.delete", role, True)

    common_checks("nfs.get_nfs3_clients", role, True, valid_role_exception=False)
    common_checks("nfs.get_nfs4_clients", role, True, valid_role_exception=False)
    common_checks("nfs.add_principal", role, True)

    common_checks("service.start", role, True, method_args=["nfs"], valid_role_exception=False)
    common_checks("service.restart", role, True, method_args=["nfs"], valid_role_exception=False)
    common_checks("service.reload", role, True, method_args=["nfs"], valid_role_exception=False)
    common_checks("service.stop", role, True, method_args=["nfs"], valid_role_exception=False)
