"""The grant plane: what middleware's `grants` array admits and refuses.

A grant is the *account-level* share — which TrueNAS accounts reach a
bucket at all — and it is the one access control nothing on the wire can
address. `sharing.s3.update` writes it, the render puts it in
`policies.conf`, and the daemon evaluates it ahead of every stored S3
ACL. So this module is the round trip: a grant set through the API,
observed over the protocol.

**`DENY` is the kill switch and it is unconditional.** It outranks the
bucket owner and every allow mode, which is what makes it usable as an
operator's immediate stop — and what makes its blast radius worth
pinning: it suspends the principal on *that bucket* and takes neither
the account listing nor any other bucket down with it.
"""

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
    name = buckets.get("denied")
    if not name:
        pytest.skip("no denied bucket: the session could not provision one")
    return name


def refusal(call_):
    with pytest.raises(Exception) as caught:
        call_()
    return code_of(caught.value)


def test_every_data_operation_refuses_under_deny(s3, denied):
    """`AccessDenied` on all of them — including reads of keys that do
    not exist, since the refusal must arrive before existence is
    consulted. A prober that could tell a denied miss from a denied hit
    would learn what the bucket holds."""
    assert refusal(lambda: s3.put_object(Bucket=denied, Key="k", Body=b"x")) == "AccessDenied"
    assert refusal(lambda: s3.get_object(Bucket=denied, Key="k")) == "AccessDenied"
    assert refusal(lambda: s3.delete_object(Bucket=denied, Key="k")) == "AccessDenied"
    assert refusal(lambda: s3.list_objects_v2(Bucket=denied)) == "AccessDenied"
    assert refusal(lambda: s3.get_object_tagging(Bucket=denied, Key="k")) == "AccessDenied"


def test_deny_outranks_the_bucket_owner(s3, denied, accounts):
    """The row this runs against is owned by the very account it denies.

    An owner ordinarily bypasses the grants, so a `DENY` that stopped at
    ownership would be an operator's stop button that did not stop the
    one account most likely to need stopping.
    """
    entry = call("sharing.s3.query", [["name", "=", denied]], {"get": True})
    assert entry["owner_uid"] == accounts["main"].uid, "the denied principal owns this bucket"
    assert refusal(lambda: s3.list_objects_v2(Bucket=denied)) == "AccessDenied"


def test_deny_is_scoped_to_its_own_bucket(s3, denied, bucket):
    """The neighbouring bucket is untouched, which is what "per bucket"
    has to mean."""
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

    Yields `(client, set_grants)`: the *grantee's* client, and a function
    that replaces the bucket's whole grant list through
    `sharing.s3.update`. The update is a reload rather than a restart, so
    the next request already sees it — which is what makes a grant change
    observable inside one test.
    """
    with (
        s3_bucket(
            BUCKET,
            dataset=DATASET,
            owner=owner.username,
            object_ownership="OBJECT_WRITER",
            grants=[],
        ) as entry,
        s3_service(),
    ):

        def set_grants(grants):
            call("sharing.s3.update", entry["id"], {"grants": grants})

        yield client_for(grantee.key, daemon), set_grants


def test_no_grant_admits_nothing(granted, grantee):
    """The bucket exists and this account is not on it, so it is not
    merely empty — it is unreachable."""
    client, _set = granted
    assert refusal(lambda: client.list_objects_v2(Bucket=BUCKET)) == "AccessDenied"
    assert refusal(lambda: client.put_object(Bucket=BUCKET, Key="k", Body=b"x")) == "AccessDenied"


def test_readonly_opens_the_reads_and_not_the_writes(granted, grantee, owner, daemon):
    """`READONLY` is the mode an operator gives a consumer, and what it
    must *not* give is any way to change what it consumes."""
    client, set_grants = granted
    owner_client = client_for(owner.key, daemon)
    owner_client.put_object(Bucket=BUCKET, Key="ro/seed.bin", Body=b"seed")

    set_grants([user_grant(grantee.uid, "READONLY")])
    assert client.get_object(Bucket=BUCKET, Key="ro/seed.bin")["Body"].read() == b"seed"
    client.list_objects_v2(Bucket=BUCKET)
    assert refusal(lambda: client.put_object(Bucket=BUCKET, Key="ro/new.bin", Body=b"x")) == "AccessDenied"
    assert refusal(lambda: client.delete_object(Bucket=BUCKET, Key="ro/seed.bin")) == "AccessDenied"


def test_writeonly_opens_the_writes_and_not_the_reads(granted, grantee):
    """The drop-box mode: a backup client that may deposit and may not
    enumerate or read back what anyone else deposited."""
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


def test_an_everyone_grant_reaches_a_principal_no_row_names(granted, grantee):
    """`EVERYONE` is every account holding a valid access key, so it
    admits a principal the grant list never mentions by uid."""
    client, set_grants = granted
    set_grants([everyone_grant("READONLY")])

    client.list_objects_v2(Bucket=BUCKET)
    assert refusal(lambda: client.put_object(Bucket=BUCKET, Key="ev/new.bin", Body=b"x")) == "AccessDenied"


def test_a_deny_row_beats_an_everyone_allow(granted, grantee):
    """Both rows match the caller and only one can win. `DENY` does,
    which is what makes it usable to suspend one account out of a bucket
    that is otherwise open to all."""
    client, set_grants = granted
    set_grants([everyone_grant("READWRITE"), user_grant(grantee.uid, "DENY")])
    assert refusal(lambda: client.list_objects_v2(Bucket=BUCKET)) == "AccessDenied"

    # And lifting the deny restores what the EVERYONE row already said.
    set_grants([everyone_grant("READWRITE")])
    client.list_objects_v2(Bucket=BUCKET)


def test_a_group_grant_admits_by_membership(granted, grantee):
    """A `GROUP` grant names a gid, and the account's own primary group
    is the membership the daemon resolves through NSS."""
    client, set_grants = granted
    set_grants([group_grant(grantee.gid, "READWRITE")])
    client.put_object(Bucket=BUCKET, Key="grp/obj.bin", Body=b"via the group")
    assert client.get_object(Bucket=BUCKET, Key="grp/obj.bin")["Body"].read() == b"via the group"


def test_removing_a_grant_closes_the_door_again(granted, grantee):
    """`grants` replaces the whole list, so an empty one is a revocation
    — and a revocation that only took effect at the next restart would be
    an operator's stop button with a delay on it."""
    client, set_grants = granted
    set_grants([user_grant(grantee.uid, "READWRITE")])
    client.put_object(Bucket=BUCKET, Key="rev/obj.bin", Body=b"x")

    set_grants([])
    assert refusal(lambda: client.get_object(Bucket=BUCKET, Key="rev/obj.bin")) == "AccessDenied"


def test_a_global_grant_reaches_every_bucket(granted, grantee, s3, bucket):
    """The service's own `global_grants` render against bucket `*`.

    A `DENY` there suspends the principal everywhere, which is the one
    control that is not per bucket — so it is asserted against a bucket
    this module never configured.
    """
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
    """The credential plane, beside the grant plane.

    A key is disabled through `s3.accesskey.update` and the render writes
    `enabled = false`; the daemon then refuses it as an unknown key
    rather than as an unauthorized one, because the store refuses before
    any signature comparison and an expired or disabled credential never
    reveals that it once existed.
    """
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
    """Rotation is a render and a reload, and the old secret stops
    signing the moment the daemon has read the new file — which is the
    point of rotating it.

    Driven on a second key of the grantee's own rather than on the
    module's shared one: a rotated secret cannot be rotated back, so
    rotating the shared key would leave every later case in this module
    signing with a value the daemon no longer holds.
    """
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
