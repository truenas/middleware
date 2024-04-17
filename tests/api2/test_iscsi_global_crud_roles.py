import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_READ", "SHARING_ISCSI_GLOBAL_READ"])
def test_read_role_can_read(unprivileged_user_fixture, role):
    common_checks(unprivileged_user_fixture, "iscsi.global.config", role, True, valid_role_exception=False)
    common_checks(unprivileged_user_fixture, "iscsi.global.sessions", role, True, valid_role_exception=False)
    common_checks(unprivileged_user_fixture, "iscsi.global.client_count", role, True, valid_role_exception=False)
    common_checks(unprivileged_user_fixture, "iscsi.global.alua_enabled", role, True, valid_role_exception=False)


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_ISCSI_READ", "SHARING_ISCSI_GLOBAL_READ"])
def test_read_role_cant_write(unprivileged_user_fixture, role):
    common_checks(unprivileged_user_fixture, "iscsi.global.update", role, False)


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_ISCSI_WRITE", "SHARING_ISCSI_GLOBAL_WRITE"])
def test_write_role_can_write(unprivileged_user_fixture, role):
    common_checks(unprivileged_user_fixture, "iscsi.global.update", role, True)
