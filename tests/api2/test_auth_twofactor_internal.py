import base64

from middlewared.test.integration.assets.account import user as create_user
from middlewared.test.integration.utils import call


def test_generate_base32_secret():
    """auth.twofactor.generate_base32_secret returns a decodable base32 secret."""
    secret = call("auth.twofactor.generate_base32_secret")
    assert isinstance(secret, str)
    # A valid base32 secret decodes without error.
    assert base64.b32decode(secret)


def test_get_user_config_defaults_for_unconfigured_user():
    """get_user_config returns the default template when a user has no 2FA row."""
    config = call("auth.twofactor.get_user_config", 999999, True)
    assert config["exists"] is False
    assert config["secret"] is None
    assert config["otp_digits"] == 6
    assert config["interval"] == 30


def test_get_user_config_and_users_config_for_local_user():
    """A local user with a renewed secret appears in both the per-user and aggregate configs."""
    with create_user(
        {
            "username": "tfa_internal_user",
            "full_name": "tfa_internal_user",
            "group_create": True,
            "password": "test1234",
        }
    ) as user_obj:
        call("user.renew_2fa_secret", user_obj["username"], {"interval": 30, "otp_digits": 6})

        user_config = call("auth.twofactor.get_user_config", user_obj["id"], True)
        assert user_config["exists"] is True
        assert user_config["secret"] is not None

        users = call("auth.twofactor.get_users_config")
        entry = next((u for u in users if u["username"] == "tfa_internal_user"), None)
        assert entry is not None
        assert entry["ad_user"] is False
        assert entry["otp_digits"] == 6
        assert entry["interval"] == 30
