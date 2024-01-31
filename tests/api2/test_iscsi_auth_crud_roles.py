import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_READ", "SHARING_ISCSI_AUTH_READ"])
def test_read_role_can_read(role):
    common_checks("iscsi.auth.query", role, True, valid_role_exception=False)


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_READ", "SHARING_ISCSI_AUTH_READ"])
def test_read_role_cant_write(role):
    common_checks("iscsi.auth.create", role, False)
    common_checks("iscsi.auth.update", role, False)
    common_checks("iscsi.auth.delete", role, False)


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_ISCSI_WRITE", "SHARING_ISCSI_AUTH_WRITE"])
def test_write_role_can_write(role):
    common_checks("iscsi.auth.create", role, True)
    common_checks("iscsi.auth.update", role, True)
    common_checks("iscsi.auth.delete", role, True)
