"""S3 access keys are the SigV4 credential pairs the TrueNAS S3 service
serves. They live in their own table, linked to local or directory
services accounts the way API keys are, and nothing in the TrueNAS API
authentication path ever reads them."""

import json
from datetime import UTC, datetime, timedelta
import re
from time import sleep

import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client, user
from middlewared.test.integration.utils import call, client, ssh

S3_USER = "s3keyuser"
ACCESS_KEY_RE = re.compile(r"^[A-Z0-9]{20}$")
SECRET_RE = re.compile(r"^[A-Za-z0-9]{40}$")
REDACTED = "********"
CREDENTIALS_CONF = "/etc/truenas_s3/credentials.conf"


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


def test_deleted_user_takes_its_keys():
    """Deleting a local account deletes every key it held."""
    with user(
        {
            "username": "s3keygone",
            "full_name": "gone",
            "group_create": True,
            "password": "test1234",
        }
    ):
        keys = [
            call("s3.accesskey.create", {"name": f"doomed key {i}", "username": "s3keygone"})["id"] for i in range(2)
        ]
        assert len(call("s3.accesskey.query", [["id", "in", keys]])) == 2

    assert call("s3.accesskey.query", [["id", "in", keys]]) == []


def test_unresolved_directory_account_flips_the_status(accesskey):
    """A directory account's key is bound to its SID. One that no longer
    resolves reads USER_MISSING, so the credentials file never carries an
    enabled row the S3 service cannot resolve."""
    call(
        "datastore.sql",
        f"UPDATE truenas_s3_accesskey SET user_identifier = 'S-1-5-21-1-2-3-4567' WHERE id = {accesskey['id']}",
    )
    entry = call("s3.accesskey.get_instance", accesskey["id"])
    assert entry["username"] is None
    assert entry["local"] is False
    assert entry["status"] == "USER_MISSING"


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


def report_usage(entries):
    """Call the private reporting method the way the S3 daemon does.

    `midclt` runs locally as root with an unset loginuid, which is the
    origin `_can_call_private_methods` admits. The daemon reaches it the
    same way over the unix socket, so the test exercises the path that
    ships instead of one the API layer only tolerates.
    """
    payload = json.dumps(entries).replace("'", "'\\''")
    return int(ssh(f"midclt call s3.accesskey.report_usage '{payload}'").strip())


def test_a_new_key_manages_no_buckets_and_has_no_use(accesskey):
    """Both fields start closed. `manage_buckets` must default to false,
    or an upgrade would widen every key that already exists."""
    assert accesskey["manage_buckets"] is False
    assert accesskey["last_used_at"] is None


def test_manage_buckets_is_settable_and_rendered(accesskey):
    """The S3 service reads the flag from the credentials file, so the
    render is the only way it reaches the daemon."""
    updated = call("s3.accesskey.update", accesskey["id"], {"manage_buckets": True})
    assert updated["manage_buckets"] is True

    call("etc.generate", "truenas_s3")
    rendered = ssh(f"cat {CREDENTIALS_CONF}")
    assert "manage_buckets = true" in rendered

    call("s3.accesskey.update", accesskey["id"], {"manage_buckets": False})
    call("etc.generate", "truenas_s3")
    assert "manage_buckets" not in ssh(f"cat {CREDENTIALS_CONF}")


def test_reported_usage_only_moves_forward(accesskey):
    """The daemon reports what it has seen since its last call. A flush
    that arrives late, or repeats after a restart, must not move a key
    backwards."""
    key = accesskey["access_key"]
    later = int(datetime.now(UTC).timestamp())
    earlier = later - 3600

    assert report_usage([{"access_key": key, "last_used": later}]) == 1
    first = call("s3.accesskey.get_instance", accesskey["id"])["last_used_at"]
    assert first is not None

    assert report_usage([{"access_key": key, "last_used": earlier}]) == 0
    assert call("s3.accesskey.get_instance", accesskey["id"])["last_used_at"] == first


def test_manage_buckets_needs_the_write_role(s3_user):
    """The flag lets a key ask middleware to create buckets, and
    middleware answers as the account the key belongs to. An account
    without the role would have every such call refused, so the key is
    refused here instead. The module's user deliberately holds no roles."""
    with pytest.raises(ValidationErrors) as ve:
        call(
            "s3.accesskey.create",
            {"name": "would-be admin", "username": S3_USER, "manage_buckets": True},
        )
    assert "manage_buckets" in ve.value.errors[0].attribute
    assert "SHARING_S3_WRITE" in ve.value.errors[0].errmsg
    assert not call("s3.accesskey.query", [["name", "=", "would-be admin"]])


@pytest.mark.parametrize("role", ["SHARING_S3_WRITE", "SHARING_WRITE"])
def test_manage_buckets_is_allowed_for_a_role_holder(role):
    """`SHARING_WRITE` includes `SHARING_S3_WRITE`, and the composed role
    list is what the check reads, so a role that merely includes it
    passes."""
    with unprivileged_user_client(roles=[role]) as c:
        key = call(
            "s3.accesskey.create",
            {"name": f"admin key {role}", "username": c.username, "manage_buckets": True},
        )
        try:
            assert key["manage_buckets"] is True
        finally:
            call("s3.accesskey.delete", key["id"])


def test_turning_manage_buckets_on_is_checked_too(accesskey):
    """The update path takes the same check, so a key cannot reach the
    flag by being created without it and edited afterwards."""
    with pytest.raises(ValidationErrors) as ve:
        call("s3.accesskey.update", accesskey["id"], {"manage_buckets": True})
    assert "manage_buckets" in ve.value.errors[0].attribute
    assert call("s3.accesskey.get_instance", accesskey["id"])["manage_buckets"] is False


def test_update_cannot_set_the_usage_timestamp(accesskey):
    """`last_used_at` is the S3 service's to move and nobody else's. The
    entry model excludes it from the update shape, and the base model
    forbids extra fields, so naming it is a validation error rather than
    a value that is quietly dropped."""
    with pytest.raises(ValidationErrors):
        call(
            "s3.accesskey.update",
            accesskey["id"],
            {"last_used_at": datetime.now(UTC).isoformat()},
        )


def test_an_ordinary_update_does_not_disturb_the_usage_timestamp(accesskey):
    """An update model-dumps the whole entry, so the stored timestamp
    travels back through compress. It must be dropped there: writing back
    what the update read would undo a flush that landed in between."""
    used = int(datetime.now(UTC).timestamp())
    assert report_usage([{"access_key": accesskey["access_key"], "last_used": used}]) == 1
    before = call("s3.accesskey.get_instance", accesskey["id"])["last_used_at"]
    assert before is not None

    renamed = call("s3.accesskey.update", accesskey["id"], {"name": "renamed key"})
    assert renamed["name"] == "renamed key"
    assert renamed["last_used_at"] == before


def test_reported_usage_skips_a_key_that_is_gone(accesskey):
    """A key deleted between its use and the next flush is ordinary, so
    it is skipped rather than failing the whole batch."""
    assert (
        report_usage(
            [
                {"access_key": "AKIAGONEGONEGONEGONE", "last_used": int(datetime.now(UTC).timestamp())},
                {"access_key": accesskey["access_key"], "last_used": int(datetime.now(UTC).timestamp())},
            ]
        )
        == 1
    )
    assert call("s3.accesskey.get_instance", accesskey["id"])["last_used_at"] is not None
