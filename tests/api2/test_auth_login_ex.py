import errno

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.account import user as create_user
from middlewared.test.integration.assets.two_factor_auth import (
    enabled_twofactor_auth,
    get_user_secret,
    get_2fa_totp_token,
)
from middlewared.test.integration.utils import call, client, password


LEGACY_VERSION = "v26.0.0"


@pytest.fixture(scope="function")
def clear_ratelimit():
    call("rate.limit.cache_clear")


def test_otp_token_without_login_in_progress():
    """Submitting an OTP token with no authentication in progress is rejected with EINVAL."""
    with client(auth=None) as c:
        with pytest.raises(CallError) as ce:
            c.call(
                "auth.login_ex",
                {
                    "mechanism": "OTP_TOKEN",
                    "otp_token": "123456",
                },
            )
        assert ce.value.errno == errno.EINVAL


def test_login_ex_continue_without_login_in_progress():
    """auth.login_ex_continue funnels into login_ex; with no progress it also errors EINVAL."""
    with client(auth=None) as c:
        with pytest.raises(CallError) as ce:
            c.call(
                "auth.login_ex_continue",
                {
                    "mechanism": "OTP_TOKEN",
                    "otp_token": "123456",
                },
            )
        assert ce.value.errno == errno.EINVAL


def test_scram_final_without_first_message():
    """A SCRAM CLIENT_FINAL_MESSAGE with no preceding CLIENT_FIRST_MESSAGE has no PAM handle."""
    with client(auth=None) as c:
        with pytest.raises(RuntimeError, match="pam handle was not initialized"):
            c.call(
                "auth.login_ex",
                {
                    "mechanism": "SCRAM",
                    "scram_type": "CLIENT_FINAL_MESSAGE",
                    "rfc_str": "c=biws,r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j,p=v0X8v3Bz2T0CJGbJQyF0X+HI4Ts=",
                },
            )


def test_password_plain_no_api_access_denied():
    """A valid local user with no privilege is refused with response_type DENIED."""
    with create_user(
        {
            "username": "noapiuser",
            "full_name": "noapiuser",
            "group_create": True,
            "password": "test1234",
        }
    ):
        with client(auth=None) as c:
            resp = c.call(
                "auth.login_ex",
                {
                    "mechanism": "PASSWORD_PLAIN",
                    "username": "noapiuser",
                    "password": "test1234",
                },
            )
            assert resp["response_type"] == "DENIED"


def test_twofactor_login_no_api_access_denied(clear_ratelimit):
    """A 2FA user with no API privilege is refused with DENIED after a valid OTP token."""
    with create_user(
        {
            "username": "twofa_noapi",
            "full_name": "twofa_noapi",
            "group_create": True,
            "password": "test1234",
        }
    ) as user_obj:
        with enabled_twofactor_auth():
            call("user.renew_2fa_secret", user_obj["username"], {"interval": 60})
            secret = get_user_secret(user_obj["id"])
            with client(auth=None) as c:
                resp = c.call(
                    "auth.login_ex",
                    {
                        "mechanism": "PASSWORD_PLAIN",
                        "username": "twofa_noapi",
                        "password": "test1234",
                    },
                )
                assert resp["response_type"] == "OTP_REQUIRED"

                resp = c.call(
                    "auth.login_ex_continue",
                    {
                        "mechanism": "OTP_TOKEN",
                        "otp_token": get_2fa_totp_token(secret),
                    },
                )
                assert resp["response_type"] == "DENIED"


def test_legacy_login_success():
    """The removed-in-v27 auth.login still authenticates root over an older API version."""
    with client(auth=None, version=LEGACY_VERSION) as c:
        assert c.call("auth.login", "root", password()) is True


def test_legacy_login_bad_password():
    """auth.login returns False for an incorrect password."""
    with client(auth=None, version=LEGACY_VERSION) as c:
        assert c.call("auth.login", "root", "wrong-password") is False


def test_legacy_login_with_twofactor(clear_ratelimit):
    """auth.login honors the OTP second factor: no token fails, the right token succeeds."""
    with create_user(
        {
            "username": "legacy2fa",
            "full_name": "legacy2fa",
            "group_create": True,
            "groups": [call("group.query", [["group", "=", "builtin_administrators"]], {"get": True})["id"]],
            "password": "test1234",
        }
    ) as user_obj:
        with enabled_twofactor_auth():
            call("user.renew_2fa_secret", user_obj["username"], {"interval": 60})
            secret = get_user_secret(user_obj["id"])

            # Password alone returns OTP_REQUIRED, which legacy login maps to False
            # when no otp_token was supplied.
            with client(auth=None, version=LEGACY_VERSION) as c:
                assert c.call("auth.login", "legacy2fa", "test1234") is False

            with client(auth=None, version=LEGACY_VERSION) as c:
                assert c.call("auth.login", "legacy2fa", "test1234", get_2fa_totp_token(secret)) is True


def test_legacy_login_with_api_key_invalid():
    """The removed-in-v27 auth.login_with_api_key returns False for a malformed key."""
    with client(auth=None, version=LEGACY_VERSION) as c:
        assert c.call("auth.login_with_api_key", "not-a-valid-key") is False
