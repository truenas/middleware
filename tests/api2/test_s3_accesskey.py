"""S3 access keys are the SigV4 credential pairs the TrueNAS S3 service
serves. They live in their own table, linked to local or directory
services accounts the way API keys are, and nothing in the TrueNAS API
authentication path ever reads them."""

from datetime import UTC, datetime, timedelta
import re
from time import sleep

import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client, user
from middlewared.test.integration.utils import call, client

S3_USER = "s3keyuser"
ACCESS_KEY_RE = re.compile(r"^[A-Z0-9]{20}$")
SECRET_RE = re.compile(r"^[A-Za-z0-9]{40}$")
REDACTED = "********"


@pytest.fixture(scope="module")
def s3_user():
    # Deliberately without privilege roles. An access key needs none.
    with user(
        {
            "username": S3_USER,
            "full_name": "S3 key user",
            "group_create": True,
            "password": "test1234",
        }
    ) as u:
        yield u


@pytest.fixture()
def accesskey(s3_user):
    key = call("s3.accesskey.create", {"name": "S3 test key", "username": S3_USER})
    try:
        yield key
    finally:
        call("s3.accesskey.delete", key["id"])


def test_create_generates_an_aws_shaped_pair(accesskey):
    """A user without privilege roles gets a generated pair whose access key
    is safe inside the credentials file's quoted section heading."""
    assert ACCESS_KEY_RE.match(accesskey["access_key"])
    assert SECRET_RE.match(accesskey["secret"])
    assert accesskey["username"] == S3_USER
    assert accesskey["local"] is True
    assert accesskey["enabled"] is True
    assert accesskey["expires_at"] is None
    assert accesskey["status"] == "ENABLED"


def test_secret_is_readable_by_write_role_only(accesskey):
    """The secret stays readable to SHARING_S3_WRITE and is redacted for a
    read-only role."""
    entry = call("s3.accesskey.get_instance", accesskey["id"])
    assert entry["secret"] == accesskey["secret"]

    with unprivileged_user_client(roles=["SHARING_S3_READ"]) as c:
        seen = c.call("s3.accesskey.get_instance", accesskey["id"])
        assert seen["access_key"] == accesskey["access_key"]
        assert seen["secret"] == REDACTED

        with pytest.raises(CallError):
            c.call("s3.accesskey.update", accesskey["id"], {"rotate": True})


def test_supplied_pair_is_accepted(s3_user):
    """A caller may bring its own pair; the access key stays unique."""
    supplied = {
        "access_key": "AKTNASSUPPLIEDKEY001",
        "secret": "supplied/secret+value%1234567890",
    }
    key = call("s3.accesskey.create", {"name": "supplied key", "username": S3_USER, **supplied})
    try:
        assert key["access_key"] == supplied["access_key"]
        assert key["secret"] == supplied["secret"]

        with pytest.raises(ValidationErrors) as ve:
            call(
                "s3.accesskey.create",
                {
                    "name": "duplicate access key",
                    "username": S3_USER,
                    "access_key": supplied["access_key"],
                },
            )
        assert "access_key must be unique" in ve.value.errors[0].errmsg

        with pytest.raises(ValidationErrors) as ve:
            call("s3.accesskey.create", {"name": "supplied key", "username": S3_USER})
        assert "name must be unique" in ve.value.errors[0].errmsg
    finally:
        call("s3.accesskey.delete", key["id"])


@pytest.mark.parametrize(
    "bad",
    [
        {"access_key": "lowercase0123456789ab"},
        {"access_key": "SHORT"},
        {"secret": "has a space in it 12345"},
        {"secret": "short"},
    ],
)
def test_malformed_pair_is_refused(s3_user, bad):
    """Anything the S3 service's config reader could not carry verbatim is
    refused up front."""
    with pytest.raises(ValidationErrors):
        call("s3.accesskey.create", {"name": "bad key", "username": S3_USER, **bad})


def test_unknown_user_is_refused():
    with pytest.raises(ValidationErrors) as ve:
        call("s3.accesskey.create", {"name": "orphan key", "username": "nosuchuser"})
    assert "User does not exist" in ve.value.errors[0].errmsg


def test_access_key_never_authenticates_to_the_api(accesskey):
    """Nothing in the API authentication path reads this table."""
    with client(auth=None) as c:
        resp = c.call(
            "auth.login_ex",
            {
                "mechanism": "API_KEY_PLAIN",
                "username": S3_USER,
                "api_key": f"{accesskey['id']}-{accesskey['secret']}",
            },
        )
    assert resp["response_type"] != "SUCCESS", resp


def test_rotate_keeps_the_access_key(accesskey):
    rotated = call("s3.accesskey.update", accesskey["id"], {"rotate": True})
    assert rotated["access_key"] == accesskey["access_key"]
    assert rotated["secret"] != accesskey["secret"]
    assert SECRET_RE.match(rotated["secret"])
    assert call("s3.accesskey.get_instance", accesskey["id"])["secret"] == rotated["secret"]


def test_update_cannot_change_the_account_or_the_pair(accesskey):
    for bad in (
        {"username": "root"},
        {"access_key": "AKTNASNEWACCESSKEY01"},
        {"secret": "a/new/secret+value1234567890"},
    ):
        with pytest.raises(ValidationErrors):
            call("s3.accesskey.update", accesskey["id"], bad)

    updated = call(
        "s3.accesskey.update",
        accesskey["id"],
        {"name": "renamed key", "enabled": False},
    )
    assert updated["name"] == "renamed key"
    assert updated["status"] == "DISABLED"
    assert updated["secret"] == accesskey["secret"]


def test_expiry_flips_the_status(s3_user):
    expires_at = datetime.now(UTC) + timedelta(seconds=3)
    key = call(
        "s3.accesskey.create",
        {"name": "expiring key", "username": S3_USER, "expires_at": expires_at},
    )
    try:
        assert key["status"] == "ENABLED"
        sleep(4)
        assert call("s3.accesskey.get_instance", key["id"])["status"] == "EXPIRED"

        with pytest.raises(ValidationErrors) as ve:
            call(
                "s3.accesskey.update",
                key["id"],
                {"expires_at": datetime.now(UTC) - timedelta(days=1)},
            )
        assert "in the past" in ve.value.errors[0].errmsg
    finally:
        call("s3.accesskey.delete", key["id"])


def test_deleted_user_flips_the_status():
    """A key whose account is gone reads USER_MISSING, so the credentials
    file never carries an enabled row the S3 service cannot resolve."""
    with user(
        {
            "username": "s3keygone",
            "full_name": "gone",
            "group_create": True,
            "password": "test1234",
        }
    ):
        key = call("s3.accesskey.create", {"name": "orphaned key", "username": "s3keygone"})

    try:
        entry = call("s3.accesskey.get_instance", key["id"])
        assert entry["username"] is None
        assert entry["status"] == "USER_MISSING"
    finally:
        call("s3.accesskey.delete", key["id"])


def test_lost_secret_flips_the_status(accesskey):
    """What a configuration restore without the secret seed leaves behind."""
    call(
        "datastore.sql",
        f"UPDATE truenas_s3_accesskey SET secret = NULL WHERE id = {accesskey['id']}",
    )
    entry = call("s3.accesskey.get_instance", accesskey["id"])
    assert entry["secret"] is None
    assert entry["status"] == "SECRET_LOST"

    rotated = call("s3.accesskey.update", accesskey["id"], {"rotate": True})
    assert rotated["status"] == "ENABLED"
    assert SECRET_RE.match(rotated["secret"])
