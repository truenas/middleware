import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_FTP_READ"])
def test_read_role_can_read(unprivileged_user_fixture, role):
    common_checks(unprivileged_user_fixture, "ftp.config", role, True, valid_role_exception=False)
    common_checks(unprivileged_user_fixture, "ftp.connection_count", role, True, valid_role_exception=False)


@pytest.mark.parametrize("role", ["SHARING_READ", "SHARING_FTP_READ"])
def test_read_role_cant_write(unprivileged_user_fixture, role):
    common_checks(unprivileged_user_fixture, "ftp.update", role, False)


@pytest.mark.parametrize("role", ["SHARING_WRITE", "SHARING_FTP_WRITE"])
def test_write_role_can_write(unprivileged_user_fixture, role):
    common_checks(unprivileged_user_fixture, "ftp.update", role, True)
    common_checks(
        unprivileged_user_fixture, "service.start", role, True, method_args=["ftp"], valid_role_exception=False
    )
    common_checks(
        unprivileged_user_fixture, "service.restart", role, True, method_args=["ftp"], valid_role_exception=False
    )
    common_checks(
        unprivileged_user_fixture, "service.reload", role, True, method_args=["ftp"], valid_role_exception=False
    )
    common_checks(
        unprivileged_user_fixture, "service.stop", role, True, method_args=["ftp"], valid_role_exception=False
    )
