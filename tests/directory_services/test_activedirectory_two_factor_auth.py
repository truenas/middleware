"""Two-factor authentication for Active Directory accounts.

Local accounts always have a row in `account.twofactor_user_auth` (`user.create` inserts
one) and it is keyed by user id. Directory services accounts have no row until 2FA is
configured for them, and the row is keyed by SID with a NULL user id. That difference is
what these tests exercise; the local side lives in tests/api2/test_account_2fa.py.
"""

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.directory_service import directoryservice
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.system import reset_systemd_svcs


def twofactor_records(sid):
    return call("datastore.query", "account.twofactor_user_auth", [["user_sid", "=", sid]])


def delete_twofactor_records(sid):
    for record in twofactor_records(sid):
        call("datastore.delete", "account.twofactor_user_auth", record["id"])


@pytest.fixture(scope="module")
def ad_user():
    reset_systemd_svcs("winbind")

    with directoryservice("ACTIVEDIRECTORY") as ad:
        entry = call(
            "user.query",
            [["username", "=", ad["account"].user_obj["pw_name"]]],
            {"get": True},
        )
        assert entry["local"] is False, entry
        assert entry["sid"] is not None, entry

        try:
            yield entry
        finally:
            # the row is keyed by SID, so it would outlive the domain membership
            delete_twofactor_records(entry["sid"])


def test_twofactor_config_without_record(ad_user):
    delete_twofactor_records(ad_user["sid"])

    assert call("user.twofactor_config", ad_user["username"]) == {
        "provisioning_uri": None,
        "secret_configured": False,
        "interval": 30,
        "otp_digits": 6,
    }

    with pytest.raises(CallError) as ve:
        call("user.provisioning_uri", ad_user["username"])

    assert "does not have two factor authentication configured" in ve.value.errmsg


def test_unset_2fa_secret_without_record(ad_user):
    """There is nothing to unset, and no record is created either."""
    delete_twofactor_records(ad_user["sid"])

    assert call("user.unset_2fa_secret", ad_user["username"]) is None

    assert twofactor_records(ad_user["sid"]) == []


def test_renew_2fa_secret_creates_record(ad_user):
    """Unlike a local user, a domain user without a record gets one inserted."""
    delete_twofactor_records(ad_user["sid"])

    entry = call("user.renew_2fa_secret", ad_user["username"], {"otp_digits": 8, "interval": 60})

    assert entry["username"] == ad_user["username"]
    twofactor_config = entry["twofactor_config"]
    assert twofactor_config["secret_configured"] is True
    assert twofactor_config["otp_digits"] == 8
    assert twofactor_config["interval"] == 60
    assert twofactor_config["provisioning_uri"].startswith("otpauth://totp/iXsystems:")

    records = twofactor_records(ad_user["sid"])
    assert len(records) == 1, records
    # the record is keyed by SID rather than by user id
    assert records[0]["user"] is None
    assert records[0]["secret"] is not None
    assert records[0]["otp_digits"] == 8
    assert records[0]["interval"] == 60

    assert call("user.twofactor_config", ad_user["username"]) == twofactor_config
    assert call("user.provisioning_uri", ad_user["username"]) == twofactor_config["provisioning_uri"]


def test_renew_2fa_secret_updates_existing_record(ad_user):
    delete_twofactor_records(ad_user["sid"])

    call("user.renew_2fa_secret", ad_user["username"], {})
    record = twofactor_records(ad_user["sid"])[0]

    call("user.renew_2fa_secret", ad_user["username"], {})

    renewed = twofactor_records(ad_user["sid"])
    assert len(renewed) == 1, renewed
    # the same row is reused, with a fresh secret
    assert renewed[0]["id"] == record["id"]
    assert renewed[0]["secret"] != record["secret"]


def test_unset_2fa_secret(ad_user):
    delete_twofactor_records(ad_user["sid"])
    call("user.renew_2fa_secret", ad_user["username"], {})

    call("user.unset_2fa_secret", ad_user["username"])

    # the row is kept, only the secret is cleared
    records = twofactor_records(ad_user["sid"])
    assert len(records) == 1, records
    assert records[0]["secret"] is None
    assert call("user.twofactor_config", ad_user["username"])["secret_configured"] is False
