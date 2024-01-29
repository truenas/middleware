import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_READ", "SHARING_ISCSI_TARGET_READ"])
def test_read_role_can_read(role):
    common_checks("iscsi.target.query", role, True, valid_role_exception=False)


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_READ", "SHARING_ISCSI_TARGET_READ"])
def test_read_role_cant_write(role):
    common_checks("iscsi.target.create", role, False)
    common_checks("iscsi.target.update", role, False)
    common_checks("iscsi.target.delete", role, False)


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_ISCSI_WRITE", "SHARING_ISCSI_TARGET_WRITE"])
def test_write_role_can_write(role):
    common_checks("iscsi.target.create", role, True)
    common_checks("iscsi.target.update", role, True)
    common_checks("iscsi.target.delete", role, True)
