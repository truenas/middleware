import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_SMB_READ"])
def test_read_role_can_read(role):
    common_checks("sharing.smb.query", role, True, valid_role_exception=False)


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_SMB_READ"])
def test_read_role_cant_write(role):
    common_checks("sharing.smb.create", role, False)
    common_checks("sharing.smb.update", role, False)
    common_checks("sharing.smb.delete", role, False)

    common_checks("sharing.smb.getacl", role, True)
    common_checks("sharing.smb.setacl", role, False)
    common_checks("smb.status", role, False)


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_SMB_WRITE"])
def test_write_role_can_write(role):
    common_checks("sharing.smb.create", role, True)
    common_checks("sharing.smb.update", role, True)
    common_checks("sharing.smb.delete", role, True)

    common_checks("sharing.smb.getacl", role, True)
    common_checks("sharing.smb.setacl", role, True)
    common_checks("smb.status", role, True, valid_role_exception=False)

    common_checks("service.start", role, True, method_args=["cifs"], valid_role_exception=False)
    common_checks("service.restart", role, True, method_args=["cifs"], valid_role_exception=False)
    common_checks("service.reload", role, True, method_args=["cifs"], valid_role_exception=False)
    common_checks("service.stop", role, True, method_args=["cifs"], valid_role_exception=False)
