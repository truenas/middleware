import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_READ", "SHARING_ISCSI_HOST_READ"])
def test_read_role_can_read(role):
    common_checks("iscsi.host.query", role, True, valid_role_exception=False)
    common_checks("iscsi.host.get_initiators", role, True)
    common_checks("iscsi.host.get_targets", role, True)


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_READ", "SHARING_ISCSI_HOST_READ"])
def test_read_role_cant_write(role):
    common_checks("iscsi.host.create", role, False)
    common_checks("iscsi.host.update", role, False)
    common_checks("iscsi.host.delete", role, False)
    common_checks("iscsi.host.set_initiators", role, False)


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_ISCSI_WRITE", "SHARING_ISCSI_HOST_WRITE"])
def test_write_role_can_write(role):
    common_checks("iscsi.host.create", role, True)
    common_checks("iscsi.host.update", role, True)
    common_checks("iscsi.host.delete", role, True)
    common_checks("iscsi.host.set_initiators", role, True)
