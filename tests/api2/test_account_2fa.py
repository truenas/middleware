import errno

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.account import user, unprivileged_user_client
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.job import assert_creates_job


def twofactor_record(user):
    return call(
        "datastore.query",
        "account.twofactor_user_auth",
        [["user_id", "=", user["id"]]],
        {"get": True},
    )


@pytest.fixture(scope="module")
def twofactor_user():
    with user(
        {
            "username": "cov2fa",
            "full_name": "cov 2fa",
            "group_create": True,
            "smb": False,
            "password": "test1234",
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
    assert twofactor_config["provisioning_uri"].startswith("otpauth://totp/iXsystems:cov2fa-")
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


def test_renew_2fa_secret_reloads_ssh(twofactor_user):
    config = call("datastore.query", "system.twofactorauthentication", [], {"get": True})
    assert config["services"] == {}

    call(
        "datastore.update",
        "system.twofactorauthentication",
        config["id"],
        {"services": {"ssh": True}},
    )
    try:
        with assert_creates_job("service.control") as job:
            assert call("user.renew_2fa_secret", "cov2fa", {})["twofactor_config"]["secret_configured"] is True

        # the new secret only reaches sshd once its configuration is reloaded
        assert call("core.get_jobs", [["id", "=", job.id]], {"get": True})["arguments"] == ["RELOAD", "ssh"]
    finally:
        call(
            "datastore.update",
            "system.twofactorauthentication",
            config["id"],
            {"services": {}},
        )
        call("user.unset_2fa_secret", "cov2fa")


def test_renew_2fa_secret_for_another_user_is_forbidden():
    with unprivileged_user_client(["READONLY_ADMIN"]) as c:
        with pytest.raises(CallError) as ve:
            c.call("user.renew_2fa_secret", "root", {})

        assert ve.value.errno == errno.EPERM
