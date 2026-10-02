import errno
import time

import pytest

from auto_config import ha
from middlewared.service_exception import CallError
from middlewared.test.integration.assets.account import temporary_update, user, unprivileged_user_client
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.two_factor_auth import (
    enabled_twofactor_auth,
    get_2fa_totp_token,
    get_user_secret,
)
from middlewared.test.integration.utils import (
    OATH_PROMPT,
    PASSWORD_PROMPT,
    call,
    ssh_auth_with_otp,
    truenas_server,
)


STANDBY_LAG = 5


def assert_ssh_auth(password_prompt, oath_prompt, login, secret=None, standby_sleep=False):
    """Assert which prompts sshd asks for, and whether the login succeeds.

    Checks the active controller, and the standby too when HA is set up. The active controller
    rebuilds /etc/users.oath and pam.d/sshd on the standby before it returns, so the standby needs
    no wait: a stale standby is the failure this asserts against.

    `secret` supplies the token to answer the OATH prompt with. Pass the superseded record to check
    that a token from it no longer authenticates.

    `standby_sleep` waits for a change that does not reach the standby synchronously.
    """
    ips = [None]
    if ha:
        ips.append(truenas_server.ha_ips()["standby"])

    for ip in ips:
        if ip and standby_sleep:
            # FIXME(vladv3458): drop `standby_sleep` once `ssh.update` and `user.update` replicate
            # through `ha_synchronization` instead of the detached `service.pre_action` hook.
            time.sleep(STANDBY_LAG)

        otp_token = ""
        if oath_prompt:
            otp_token = get_2fa_totp_token(secret)

        result = ssh_auth_with_otp("cov2fa", "test1234", otp_token, ip=ip)
        assert any(PASSWORD_PROMPT in prompt for prompt in result.prompts) is password_prompt, (ip, result)
        assert any(OATH_PROMPT in prompt for prompt in result.prompts) is oath_prompt, (ip, result)
        assert result.authenticated is login, (ip, result)


def twofactor_record(user):
    return call(
        "datastore.query",
        "account.twofactor_user_auth",
        [["user_id", "=", user["id"]]],
        {"get": True},
    )


@pytest.fixture(scope="module")
def twofactor_user():
    with dataset("cov2fa_homedir") as homedir:
        with user(
            {
                "username": "cov2fa",
                "full_name": "cov 2fa",
                "group_create": True,
                "smb": False,
                "password": "test1234",
                # `ssh_password_enabled` is what earns the user a `Match` block in sshd_config,
                # and it is rejected while the home directory is still the default
                "home": f"/mnt/{homedir}",
                "ssh_password_enabled": True,
            }
        ) as u:
            yield u


def test_twofactor_config_without_secret(twofactor_user):
    assert call("user.twofactor_config", "cov2fa") == {
        "provisioning_uri": None,
        "secret_configured": False,
        "interval": 30,
        "otp_digits": 6,
    }


def test_provisioning_uri_without_secret(twofactor_user):
    with pytest.raises(CallError) as ve:
        call("user.provisioning_uri", "cov2fa")

    assert "does not have two factor authentication configured" in ve.value.errmsg


def test_twofactor_config_nonexistent_user():
    with pytest.raises(CallError) as ve:
        call("user.twofactor_config", "cov_nonexistent_2fa")

    assert ve.value.errno == errno.ENOENT


def test_renew_2fa_secret(twofactor_user):
    assert twofactor_record(twofactor_user)["secret"] is None

    entry = call("user.renew_2fa_secret", "cov2fa", {"otp_digits": 8, "interval": 60})

    assert entry["username"] == "cov2fa"
    twofactor_config = entry["twofactor_config"]
    assert twofactor_config["secret_configured"] is True
    assert twofactor_config["otp_digits"] == 8
    assert twofactor_config["interval"] == 60
    assert twofactor_config["provisioning_uri"].startswith("otpauth://totp/TrueNAS:cov2fa-")
    assert "digits=8" in twofactor_config["provisioning_uri"]
    assert "period=60" in twofactor_config["provisioning_uri"]

    # the provisioning URI is also retrievable on its own
    assert call("user.provisioning_uri", "cov2fa") == twofactor_config["provisioning_uri"]
    assert call("user.twofactor_config", "cov2fa") == twofactor_config

    record = twofactor_record(twofactor_user)
    assert record["secret"] is not None

    # renewing again replaces the secret in place, it does not just set one
    renewed = call("user.renew_2fa_secret", "cov2fa", {"otp_digits": 8, "interval": 60})

    renewed_record = twofactor_record(twofactor_user)
    assert renewed_record["id"] == record["id"]
    assert renewed_record["secret"] != record["secret"]
    assert renewed["twofactor_config"]["provisioning_uri"] != twofactor_config["provisioning_uri"]


def test_unset_2fa_secret(twofactor_user):
    call("user.unset_2fa_secret", "cov2fa")

    assert call("user.twofactor_config", "cov2fa")["secret_configured"] is False


def test_2fa_without_database_record(twofactor_user):
    record = twofactor_record(twofactor_user)
    call("datastore.delete", "account.twofactor_user_auth", record["id"])
    try:
        # there is no secret to unset
        assert call("user.unset_2fa_secret", "cov2fa") is None

        # but a local user must always have a record in order to renew it
        with pytest.raises(CallError) as ve:
            call("user.renew_2fa_secret", "cov2fa", {})

        assert "Unable to locate two factor authentication configuration" in ve.value.errmsg
    finally:
        call(
            "datastore.insert",
            "account.twofactor_user_auth",
            {"secret": None, "user": twofactor_user["id"]},
        )


def test_2fa_secret_over_ssh(twofactor_user):
    assert call("user.renew_2fa_secret", "cov2fa", {})["twofactor_config"]["secret_configured"] is True
    secret = get_user_secret(twofactor_user["id"])

    # the secret exists, but 2FA for ssh is off, so pam.d/sshd has no pam_oath yet
    assert_ssh_auth(password_prompt=True, oath_prompt=False, login=True)

    with enabled_twofactor_auth(ssh=True):
        # enabling 2FA for ssh regenerated pam.d/sshd, so sshd now asks for the token
        assert_ssh_auth(password_prompt=True, oath_prompt=True, login=True, secret=secret)

        # a renewal replaces the secret, so a token from the previous one stops working
        call("user.renew_2fa_secret", "cov2fa", {})
        renewed_secret = get_user_secret(twofactor_user["id"])
        assert_ssh_auth(password_prompt=True, oath_prompt=True, login=False, secret=secret)
        assert_ssh_auth(password_prompt=True, oath_prompt=True, login=True, secret=renewed_secret)

        call("user.unset_2fa_secret", "cov2fa")

        # unsetting dropped the user from /etc/users.oath, so pam_oath no longer knows them
        assert_ssh_auth(password_prompt=True, oath_prompt=False, login=False)


@pytest.mark.parametrize(
    "passwordauth,twofactor_ssh,ssh_password_enabled,expect_login,expect_oath",
    [
        (True, False, True, True, False),
        (True, True, True, True, True),
        (False, False, True, False, False),
        # 2FA for ssh must not grant a password login that `passwordauth` denies
        (False, True, True, False, False),
        (True, False, False, False, False),
        (True, True, False, False, False),
        (False, False, False, False, False),
        (False, True, False, False, False),
    ],
)
def test_ssh_auth_combinations(
    twofactor_user, passwordauth, twofactor_ssh, ssh_password_enabled, expect_login, expect_oath
):
    call("user.renew_2fa_secret", "cov2fa", {})
    secret = get_user_secret(twofactor_user["id"])
    original_passwordauth = call("ssh.config")["passwordauth"]
    try:
        call("ssh.update", {"passwordauth": passwordauth})
        with temporary_update(twofactor_user, {"ssh_password_enabled": ssh_password_enabled}):
            with enabled_twofactor_auth(ssh=twofactor_ssh):
                assert_ssh_auth(
                    password_prompt=expect_login,
                    oath_prompt=expect_oath,
                    login=expect_login,
                    secret=secret,
                    standby_sleep=True,
                )
    finally:
        call("ssh.update", {"passwordauth": original_passwordauth})
        call("user.unset_2fa_secret", "cov2fa")


def test_renew_2fa_secret_for_another_user_is_forbidden():
    with unprivileged_user_client(["READONLY_ADMIN"]) as c:
        with pytest.raises(CallError) as ve:
            c.call("user.renew_2fa_secret", "root", {})

        assert ve.value.errno == errno.EPERM
