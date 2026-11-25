"""The grant plane: a grant set through `sharing.s3.update`, observed
over the protocol.

The allow modes are driven on a `BUCKET_OWNER_ENFORCED` bucket. With a
live ACL surface the evaluator defers to the object's own record, so
what a mode carries is not observable there.
"""

import json

from middlewared.test.integration.assets.s3 import (
    everyone_grant,
    group_grant,
    s3_access_key,
    s3_account,
    s3_bucket,
    s3_service,
    user_grant,
)
from middlewared.test.integration.utils import call, pool
import pytest
from s3_client import client_for, code_of, status_of

DATASET = f"{pool}/s3proto-grants"
BUCKET = "s3proto-grants"


# ── the kill switch, on the session's denied row ─────────────────────


@pytest.fixture(scope="module")
def denied(buckets):
    return buckets["denied"]


def refusal(call_):
    with pytest.raises(Exception) as caught:
        call_()
    return code_of(caught.value)


def test_every_data_operation_refuses_under_deny(s3, denied):
    """`AccessDenied` on all of them, keys that do not exist included."""
    assert refusal(lambda: s3.put_object(Bucket=denied, Key="k", Body=b"x")) == "AccessDenied"
    assert refusal(lambda: s3.get_object(Bucket=denied, Key="k")) == "AccessDenied"
    assert refusal(lambda: s3.delete_object(Bucket=denied, Key="k")) == "AccessDenied"
    assert refusal(lambda: s3.list_objects_v2(Bucket=denied)) == "AccessDenied"
    assert refusal(lambda: s3.get_object_tagging(Bucket=denied, Key="k")) == "AccessDenied"


def test_deny_outranks_the_bucket_owner(s3, denied, accounts):
    """The denied row is owned by the account it denies."""
    entry = call("sharing.s3.query", [["name", "=", denied]], {"get": True})
    assert entry["owner_uid"] == accounts["main"].uid, "the denied principal owns this bucket"
    assert refusal(lambda: s3.list_objects_v2(Bucket=denied)) == "AccessDenied"


def test_deny_is_scoped_to_its_own_bucket(s3, denied, bucket):
    s3.put_object(Bucket=bucket, Key="grants/unaffected.bin", Body=b"x")
    assert s3.get_object(Bucket=bucket, Key="grants/unaffected.bin")["Body"].read() == b"x"


# ── the allow modes, set through the API and observed over S3 ────────


@pytest.fixture(scope="module")
def grantee():
    """An account with a key and no bucket of its own."""
    with s3_account("s3protogrant") as account:
        yield account


@pytest.fixture(scope="module")
def owner():
    with s3_account("s3protoowner") as account:
        yield account


@pytest.fixture
def granted(owner, grantee, daemon):
    """A bucket owned by one account, whose grant list a case rewrites.

    Yields `(client, set_grants)`: the grantee's client, and a function
    replacing the whole grant list through `sharing.s3.update`.
    """
    with (
        s3_bucket(
            BUCKET,
            dataset=DATASET,
            owner=owner.username,
            # Enforced ownership consults no stored ACL, so what a case
            # observes is the grant alone.
            object_ownership="BUCKET_OWNER_ENFORCED",
            grants=[],
        ) as entry,
        s3_service(),
    ):

        def set_grants(grants):
            call("sharing.s3.update", entry["id"], {"grants": grants})

        yield client_for(grantee.key, daemon), set_grants


def test_no_grant_admits_nothing(granted, grantee):
    client, _set = granted
    assert refusal(lambda: client.list_objects_v2(Bucket=BUCKET)) == "AccessDenied"
    assert refusal(lambda: client.put_object(Bucket=BUCKET, Key="k", Body=b"x")) == "AccessDenied"


def test_readonly_opens_the_reads_and_not_the_writes(granted, grantee, owner, daemon):
    client, set_grants = granted
    owner_client = client_for(owner.key, daemon)
    owner_client.put_object(Bucket=BUCKET, Key="ro/seed.bin", Body=b"seed")

    set_grants([user_grant(grantee.uid, "READONLY")])
    assert client.get_object(Bucket=BUCKET, Key="ro/seed.bin")["Body"].read() == b"seed"
    client.list_objects_v2(Bucket=BUCKET)
    assert refusal(lambda: client.put_object(Bucket=BUCKET, Key="ro/new.bin", Body=b"x")) == "AccessDenied"
    assert refusal(lambda: client.delete_object(Bucket=BUCKET, Key="ro/seed.bin")) == "AccessDenied"


def test_writeonly_opens_the_writes_and_not_the_reads(granted, grantee):
    client, set_grants = granted
    set_grants([user_grant(grantee.uid, "WRITEONLY")])

    client.put_object(Bucket=BUCKET, Key="wo/dropped.bin", Body=b"x")
    assert refusal(lambda: client.get_object(Bucket=BUCKET, Key="wo/dropped.bin")) == "AccessDenied"
    assert refusal(lambda: client.list_objects_v2(Bucket=BUCKET)) == "AccessDenied"


def test_readwrite_opens_both(granted, grantee):
    client, set_grants = granted
    set_grants([user_grant(grantee.uid, "READWRITE")])

    client.put_object(Bucket=BUCKET, Key="rw/obj.bin", Body=b"both")
    assert client.get_object(Bucket=BUCKET, Key="rw/obj.bin")["Body"].read() == b"both"
    client.delete_object(Bucket=BUCKET, Key="rw/obj.bin")


def test_an_action_list_opens_exactly_those_actions(granted, grantee, owner, daemon):
    client, set_grants = granted
    client_for(owner.key, daemon).put_object(Bucket=BUCKET, Key="list/seed.bin", Body=b"seed")

    set_grants([user_grant(grantee.uid, ["GetObject", "PutObject"])])
    entry = call("sharing.s3.query", [["name", "=", BUCKET]], {"get": True})
    assert entry["grants"][0]["access"] == ["GetObject", "PutObject"]
    assert client.get_object(Bucket=BUCKET, Key="list/seed.bin")["Body"].read() == b"seed"
    client.put_object(Bucket=BUCKET, Key="list/new.bin", Body=b"x")
    assert refusal(lambda: client.list_objects_v2(Bucket=BUCKET)) == "AccessDenied"
    assert refusal(lambda: client.delete_object(Bucket=BUCKET, Key="list/seed.bin")) == "AccessDenied"


@pytest.mark.parametrize("access", [
    ["ReleaseObjectLegalHold"],
    ["BypassGovernanceRetention"],
    ["PutBucketPolicy"],
    ["GetObject", "GetObject"],
    [],
])
def test_a_list_the_service_would_refuse_is_refused_here(granted, grantee, access):
    """The service refuses its whole config over one bad name."""
    _client, set_grants = granted
    with pytest.raises(Exception):
        set_grants([user_grant(grantee.uid, access)])


def test_an_everyone_grant_reaches_a_principal_no_row_names(granted, grantee):
    """`EVERYONE` is every account holding a valid access key."""
    client, set_grants = granted
    set_grants([everyone_grant("READONLY")])

    client.list_objects_v2(Bucket=BUCKET)
    assert refusal(lambda: client.put_object(Bucket=BUCKET, Key="ev/new.bin", Body=b"x")) == "AccessDenied"


def test_a_deny_row_beats_an_everyone_allow(granted, grantee):
    client, set_grants = granted
    set_grants([everyone_grant("READWRITE"), user_grant(grantee.uid, "DENY")])
    assert refusal(lambda: client.list_objects_v2(Bucket=BUCKET)) == "AccessDenied"

    # And lifting the deny restores what the EVERYONE row already said.
    set_grants([everyone_grant("READWRITE")])
    client.list_objects_v2(Bucket=BUCKET)


def test_a_group_grant_admits_by_membership(granted, grantee):
    """The grantee's primary group is the membership resolved here."""
    client, set_grants = granted
    set_grants([group_grant(grantee.gid, "READWRITE")])
    client.put_object(Bucket=BUCKET, Key="grp/obj.bin", Body=b"via the group")
    assert client.get_object(Bucket=BUCKET, Key="grp/obj.bin")["Body"].read() == b"via the group"


def test_removing_a_grant_closes_the_door_again(granted, grantee):
    """An empty list is a revocation, in force on the next request."""
    client, set_grants = granted
    set_grants([user_grant(grantee.uid, "READWRITE")])
    client.put_object(Bucket=BUCKET, Key="rev/obj.bin", Body=b"x")

    set_grants([])
    assert refusal(lambda: client.get_object(Bucket=BUCKET, Key="rev/obj.bin")) == "AccessDenied"


def test_the_rows_read_back_as_the_bucket_policy(granted, grantee, owner, daemon):
    """No row, no policy: `NoSuchBucketPolicy`. A row reads back as one
    statement. Asked as the owner, who needs no row to ask."""
    _client, set_grants = granted
    owner_client = client_for(owner.key, daemon)

    assert refusal(lambda: owner_client.get_bucket_policy(Bucket=BUCKET)) == "NoSuchBucketPolicy"
    assert refusal(lambda: owner_client.get_bucket_policy_status(Bucket=BUCKET)) == "NoSuchBucketPolicy"

    set_grants([user_grant(grantee.uid, ["GetObject", "PutObject"])])
    [statement] = json.loads(owner_client.get_bucket_policy(Bucket=BUCKET)["Policy"])["Statement"]
    assert statement["Effect"] == "Allow"
    assert statement["Principal"] == {"AWS": f"arn:aws:iam::{grantee.uid}:user/{grantee.username}"}
    assert sorted(statement["Action"]) == ["s3:GetObject", "s3:PutObject"]
    assert statement["Resource"] == [f"arn:aws:s3:::{BUCKET}", f"arn:aws:s3:::{BUCKET}/*"]
    assert owner_client.get_bucket_policy_status(Bucket=BUCKET)["PolicyStatus"]["IsPublic"] is False

    set_grants([])
    assert refusal(lambda: owner_client.get_bucket_policy(Bucket=BUCKET)) == "NoSuchBucketPolicy"


def test_a_global_grant_reaches_every_bucket(granted, grantee, s3, bucket):
    """`global_grants` render against bucket `*`: a `DENY` there reaches
    a bucket this module never configured."""
    client, set_grants = granted
    set_grants([user_grant(grantee.uid, "READWRITE")])
    client.put_object(Bucket=BUCKET, Key="glob/obj.bin", Body=b"x")

    was = call("s3.config")["global_grants"]
    call("s3.update", {"global_grants": [user_grant(grantee.uid, "DENY")]})
    try:
        assert refusal(lambda: client.get_object(Bucket=BUCKET, Key="glob/obj.bin")) == "AccessDenied"
        # And the session's own bucket, which this module never touched.
        assert refusal(lambda: client.list_objects_v2(Bucket=bucket)) == "AccessDenied"
        # The main principal is unaffected: a global grant names one uid.
        s3.list_objects_v2(Bucket=bucket)
    finally:
        call("s3.update", {"global_grants": [{k: v for k, v in g.items() if k != "name"} for g in was]})

    assert client.get_object(Bucket=BUCKET, Key="glob/obj.bin")["Body"].read() == b"x"


def test_a_disabled_key_stops_signing(grantee, daemon, granted):
    """A disabled key is refused as an unknown one: `InvalidAccessKeyId`."""
    client, set_grants = granted
    set_grants([user_grant(grantee.uid, "READWRITE")])
    client.put_object(Bucket=BUCKET, Key="key/obj.bin", Body=b"x")

    call("s3.accesskey.update", grantee.key["id"], {"enabled": False})
    try:
        with pytest.raises(Exception) as caught:
            client.get_object(Bucket=BUCKET, Key="key/obj.bin")
        assert status_of(caught.value) == 403
        assert code_of(caught.value) == "InvalidAccessKeyId"
    finally:
        call("s3.accesskey.update", grantee.key["id"], {"enabled": True})

    assert client.get_object(Bucket=BUCKET, Key="key/obj.bin")["Body"].read() == b"x"


def test_a_rotated_secret_takes_effect_on_the_next_request(grantee, daemon, granted):
    """Driven on a second key of the grantee's: a rotated secret cannot
    be rotated back, and the module's shared key has to keep signing."""
    client, set_grants = granted
    set_grants([user_grant(grantee.uid, "READWRITE")])
    client.put_object(Bucket=BUCKET, Key="rot/obj.bin", Body=b"x")

    with s3_access_key(grantee.username, name="s3proto rotation key") as spare:
        spare_client = client_for(spare, daemon)
        assert spare_client.get_object(Bucket=BUCKET, Key="rot/obj.bin")["Body"].read() == b"x"

        rotated = call("s3.accesskey.update", spare["id"], {"rotate": True})
        assert rotated["access_key"] == spare["access_key"], "the id is stable"
        assert rotated["secret"] != spare["secret"]

        with pytest.raises(Exception) as caught:
            spare_client.get_object(Bucket=BUCKET, Key="rot/obj.bin")
        assert code_of(caught.value) == "SignatureDoesNotMatch"

        fresh = client_for(rotated, daemon)
        assert fresh.get_object(Bucket=BUCKET, Key="rot/obj.bin")["Body"].read() == b"x"
