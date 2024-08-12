import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_READ", "SHARING_ISCSI_TARGETEXTENT_READ"])
def test_read_role_can_read(unprivileged_user_fixture, role):
    common_checks(unprivileged_user_fixture, "iscsi.targetextent.query", role, True, valid_role_exception=False)


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_READ", "SHARING_ISCSI_TARGETEXTENT_READ"])
def test_read_role_cant_write(unprivileged_user_fixture, role):
    common_checks(unprivileged_user_fixture, "iscsi.targetextent.create", role, False)
    common_checks(unprivileged_user_fixture, "iscsi.targetextent.update", role, False)
    common_checks(unprivileged_user_fixture, "iscsi.targetextent.delete", role, False)


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_ISCSI_WRITE", "SHARING_ISCSI_TARGETEXTENT_WRITE"])
def test_write_role_can_write(unprivileged_user_fixture, role):
    common_checks(unprivileged_user_fixture, "iscsi.targetextent.create", role, True)
    common_checks(unprivileged_user_fixture, "iscsi.targetextent.update", role, True)
    common_checks(unprivileged_user_fixture, "iscsi.targetextent.delete", role, True)
