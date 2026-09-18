"""The deployment every S3 protocol module drives: accounts, buckets, a
running service, and the clients that reach it.

Everything here is session-scoped, because standing it up is the
expensive part and none of it varies per test. A bucket is a ZFS dataset
the daemon registers at start-up, so making one per test would cost a
registration per test and nothing would be proved by it.

**What that costs a module is that the buckets are shared.** A module
that writes keys under a prefix drains that prefix, before and after; a
module that opens a multipart upload aborts it. `ListMultipartUploads`
and a flat listing both answer for the whole bucket, so anything left
behind decides another module's page.

**The bucket set is the matrix, not a convenience.** Object lock latches
at registration, a bucket's ETag mode and object ownership are read per
bucket, and the snapshot layer composes with two different versioning
states — so each of those needs a bucket configured for it beside one
that is not. `buckets` carries them by what they prove, and **every one
of them is required**: a row that will not provision fails the session
here rather than skipping its module, because a suite that reports green
having silently declined to test object lock is worse than one that
fails.
"""

import contextlib

from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.assets.s3 import (
    DEFAULT_S3_PORT,
    s3_access_key,
    s3_account,
    s3_bucket,
    s3_endpoint,
    s3_service,
    user_grant,
    wait_for_listener,
)
from middlewared.test.integration.utils import call, pool
import pytest
from s3_client import client_for

#: Every dataset and bucket this suite makes carries it, so a leftover
#: from an interrupted run is identifiable and removable.
PREFIX = "s3proto"

MAIN_USER = f"{PREFIX}main"
ALT_USER = f"{PREFIX}alt"


def dataset_for(leaf: str) -> str:
    return f"{pool}/{PREFIX}-{leaf}"


def bucket_name(leaf: str) -> str:
    return f"{PREFIX}-{leaf}"


@pytest.fixture(scope="session")
def s3_clean_slate():
    """Remove what an interrupted run left behind.

    **Ordered ahead of everything this suite makes, which is the whole
    point.** Every name here is matched by prefix, so running it after
    the accounts exist deletes the keys the session just created — the
    service then holds no credential for them and every signed request
    answers `InvalidAccessKeyId`, which is a whole run's worth of
    failures with one cause.

    Rows before datasets: deregistering a bucket keeps its dataset on
    purpose, so a run that died between the two leaves a dataset whose
    name this run's create needs. A leftover that will not go is not
    suppressed into silence — the create that follows fails on the name,
    which says the same thing louder.
    """
    for row in call("sharing.s3.query", [["name", "^", f"{PREFIX}-"]]):
        with contextlib.suppress(Exception):
            call("sharing.s3.delete", row["id"])
    for row in call("s3.accesskey.query", [["name", "^", PREFIX]]):
        with contextlib.suppress(Exception):
            call("s3.accesskey.delete", row["id"])
    for row in call("user.query", [["username", "^", PREFIX]]):
        with contextlib.suppress(Exception):
            call("user.delete", row["id"])
    for row in call("zfs.resource.list", {"paths": [pool], "properties": None, "get_children": True}):
        if row["name"].startswith(f"{pool}/{PREFIX}-"):
            with contextlib.suppress(Exception):
                call("zfs.resource.destroy", {"path": row["name"], "recursive": True})


def _prove_signable(client, label: str) -> None:
    """Fail the session unless the S3 service holds this key.

    A credential the service does not hold refuses *every* request, so a
    suite that did not check would report hundreds of failures with one
    cause — and would pass, spuriously, every case that asserts a bare
    403. `alt` legitimately has nothing to list, so the assertion is on
    the credential layer alone rather than on the call succeeding.
    """
    import botocore.exceptions

    try:
        client.list_buckets()
    except botocore.exceptions.ClientError as err:
        code = err.response["Error"]["Code"]
        assert code not in ("InvalidAccessKeyId", "SignatureDoesNotMatch"), (
            f"{label}: the S3 service does not hold this key ({code}). "
            f"Every signed request this session makes would be refused."
        )


@pytest.fixture(scope="session")
def s3_licensed():
    """The two licensed S3 features, answered entitled for the session.

    Object versioning and the audit trail are licensed, and both gates
    are consulted twice: `sharing.s3.create` refuses a versioned row
    without the first, and the *daemon* asks for both at start-up and
    brings the deployment down to what they say — a bucket configured
    for versioning is served suspended, and one configured for object
    lock is excluded and answers 503.

    So this has to be in force before the service starts, not merely
    before a bucket is created, or the conformance modules would drive a
    matrix the daemon had already taken apart.
    """
    with entitled("S3_VERSIONING"), entitled("S3_AUDIT"):
        yield


@pytest.fixture(scope="session")
def s3_accounts(s3_licensed, s3_clean_slate):
    """The two principals the matrix needs, and their keys.

    `main` owns most of the buckets and holds a grant on each, so it is
    the account nearly everything is driven as. It holds
    `SHARING_S3_WRITE` for one reason only: `manage_buckets` is refused
    on a key whose account could not spend it, and the bucket-plane
    module needs such a key. The role scopes the *account*; the flag
    scopes the *key*, and `main.key` deliberately does not carry it — a
    refusal is attributable to the flag only where the two keys differ
    in nothing else.

    `alt` holds no roles and no grant anywhere. What admits it to
    anything is a stored S3 ACL and nothing else, which is what makes it
    the principal the enforcement half of the ACL matrix is driven as.
    """
    with (
        s3_account(MAIN_USER, roles=["SHARING_S3_WRITE"]) as main,
        s3_access_key(MAIN_USER, name=f"{PREFIX} admin key", manage_buckets=True) as admin_key,
        s3_account(ALT_USER) as alt,
    ):
        main.admin_key = admin_key
        yield {"main": main, "alt": alt}


@pytest.fixture(scope="session")
def s3_deployment(s3_accounts):
    """Every bucket, then a running service that has registered them.

    The order is the whole of this fixture. Buckets are made while the
    service is down, so the registration each one costs is paid once at
    the start rather than per create; the excluded row's dataset is
    destroyed *before* the start, so the daemon meets the row already
    unservable and answers 503 for it rather than having to be restarted
    into that state; and the listener is waited for, because a fresh
    dataset costs a directory fanout before the socket ever accepts.
    """
    main = s3_accounts["main"]

    # Every row grants `main` and nothing else: `alt` reaching anything
    # is what a stored ACL has to explain.
    mine = [user_grant(main.uid)]
    rows = {
        # The ordinary bucket. `OBJECT_WRITER` rather than the default
        # `BUCKET_OWNER_ENFORCED`, because enforced ownership disables
        # the S3 ACL surface outright — the record is neither minted nor
        # consulted — and every ACL module here needs it live.
        "attached": {"object_ownership": "OBJECT_WRITER", "owner": MAIN_USER, "grants": mine},
        # Versioned and locked: the latch is stamped on the dataset root
        # at registration, so it cannot be a bucket anything else uses.
        "locked": {
            "object_ownership": "OBJECT_WRITER",
            "owner": MAIN_USER,
            "grants": mine,
            "versioning": "ENABLED",
            "object_lock": True,
        },
        # The same, carrying a default retention rule a silent create
        # inherits.
        "defaulted": {
            "object_ownership": "OBJECT_WRITER",
            "owner": MAIN_USER,
            "grants": mine,
            "versioning": "ENABLED",
            "object_lock": True,
            "object_lock_default_mode": "GOVERNANCE",
            "object_lock_default_days": 1,
        },
        # The snapshot layer's two compositions: suspended, so ZFS holds
        # the history, and never-versioned, which is ZFS history alone
        # behind the empty versioning document.
        "history": {
            "object_ownership": "OBJECT_WRITER",
            "owner": MAIN_USER,
            "grants": mine,
            "versioning": "SUSPENDED",
            "snapshot_versions": ["s3-*"],
        },
        "attic": {
            "object_ownership": "OBJECT_WRITER",
            "owner": MAIN_USER,
            "grants": mine,
            "snapshot_versions": ["s3-*"],
        },
        # The row that declines the part digest. Its answer is per
        # bucket, so proving it needs one that carries it beside one
        # that does not.
        "minted": {
            "object_ownership": "OBJECT_WRITER",
            "owner": MAIN_USER,
            "grants": mine,
            "multipart_etag": "MINTED",
        },
        # Conditional object ownership, **owned by `alt` and written by
        # `main`**: under `BUCKET_OWNER_PREFERRED` a write records the
        # caller unless it carried `bucket-owner-full-control`, and a
        # bucket whose owner is already its writer answers both ways
        # identically. The grant below is what admits `main` to write
        # here; `alt` owns it and grants nothing.
        "preferred": {
            "object_ownership": "BUCKET_OWNER_PREFERRED",
            "owner": ALT_USER,
            "grants": mine,
        },
        # The kill switch: a `DENY` grant naming the bucket's own owner,
        # which outranks ownership and suspends the principal here alone.
        "denied": {
            "object_ownership": "OBJECT_WRITER",
            "owner": MAIN_USER,
            "grants": [user_grant(main.uid, "DENY")],
        },
        # A row the daemon will refuse to register: made whole, then its
        # dataset destroyed under it, which is the only way to reach the
        # answer an unservable bucket owes.
        "excluded": {"object_ownership": "OBJECT_WRITER", "owner": MAIN_USER, "grants": mine},
    }

    # **Every row is required, and a failure here fails the session.**
    # Nothing in the set above has an environmental precondition this
    # lane does not meet: there is a pool, `sharing.s3.create` makes the
    # datasets, and the two licensed features are mocked entitled above.
    # So a row that will not provision is the defect the suite exists to
    # find — and tolerating it would skip that row's whole module and
    # report the run green.
    with contextlib.ExitStack() as stack:
        made = {
            leaf: stack.enter_context(s3_bucket(bucket_name(leaf), dataset=dataset_for(leaf), **options))
            for leaf, options in rows.items()
        }

        # Not `pool.dataset.delete`, which runs the share attachment
        # delegates and would deregister the bucket with it. The row has
        # to stand while its storage does not.
        call("zfs.resource.destroy", {"path": made["excluded"]["dataset"], "recursive": True})

        with s3_service():
            wait_for_listener(DEFAULT_S3_PORT)
            endpoint = s3_endpoint(DEFAULT_S3_PORT)

            # The credentials reached the service, before a single case
            # depends on it. Checked here rather than left to the first
            # test because the failure is indistinguishable per-test from
            # an authorization one, and silent in every case that asserts
            # a bare 403.
            for label, key in (
                ("main", main.key),
                ("admin", main.admin_key),
                ("alt", s3_accounts["alt"].key),
            ):
                _prove_signable(client_for(key, endpoint), label)

            yield {
                "endpoint": endpoint,
                "accounts": s3_accounts,
                "buckets": {leaf: entry["name"] for leaf, entry in made.items()},
                "entries": made,
            }


# ── what a module asks for ───────────────────────────────────────────


@pytest.fixture(scope="session")
def daemon(s3_deployment):
    """The endpoint the S3 service answers on."""
    return s3_deployment["endpoint"]


@pytest.fixture(scope="session")
def buckets(s3_deployment):
    """Every bucket by what it proves, `None` where there is none."""
    return s3_deployment["buckets"]


@pytest.fixture(scope="session")
def bucket(buckets):
    """The bucket that serves — what most cases want."""
    return buckets["attached"]


@pytest.fixture(scope="session")
def accounts(s3_deployment):
    """The two principals, for the cases that need a uid or a name."""
    return s3_deployment["accounts"]


@pytest.fixture(scope="session")
def s3(s3_deployment):
    """The client every case takes unless it says otherwise."""
    return client_for(s3_deployment["accounts"]["main"].key, s3_deployment["endpoint"])


@pytest.fixture(scope="session")
def s3_unsummed(s3_deployment):
    """The same client with the SDK's default checksum turned off.

    Modern botocore sends `x-amz-checksum-crc32` on every upload, so "an
    object written with no checksum" is otherwise unreachable through
    the SDK.
    """
    return client_for(
        s3_deployment["accounts"]["main"].key,
        s3_deployment["endpoint"],
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
    )


@pytest.fixture(scope="session")
def admin_s3(s3_deployment):
    """The same account as `s3`, on a key that carries `manage_buckets`.

    The operations middleware owns are gated on the key before any of
    them reaches a connector, so a case about what the *connector*
    answers has to clear that gate first or it is only re-proving the
    gate.
    """
    return client_for(s3_deployment["accounts"]["main"].admin_key, s3_deployment["endpoint"])


@pytest.fixture
def wildcard_grant(accounts):
    """A grant over every bucket, for the duration of one case.

    **403 precedes existence.** Authorization runs before the engine is
    consulted, so a caller with no grant for a name cannot tell an
    unconfigured bucket from an unservable one from a name the grammar
    refuses — all three are the same bare `AccessDenied`, which is what
    stops error codes being used to map what exists.

    `main` holds per-bucket grants, so it can never see past that for a
    name it does not own. A case that is *about* one of those answers
    takes this: a global grant renders against bucket `*` and reaches
    every name, including ones nothing holds a row for, and the
    operation's own answer surfaces. Restored on the way out, because
    the grant coverage of every other module depends on `main` reaching
    only what its own rows name.
    """
    was = call("s3.config")["global_grants"]
    call("s3.update", {"global_grants": [user_grant(accounts["main"].uid)]})
    try:
        yield
    finally:
        call("s3.update", {"global_grants": [{k: v for k, v in g.items() if k != "name"} for g in was]})


@pytest.fixture(scope="session")
def alt_s3(s3_deployment):
    """The second principal: authenticated, holding no grant anywhere.

    Every allow it observes travelled through a stored ACL, which is the
    deferral this server's authorization rests on.
    """
    return client_for(s3_deployment["accounts"]["alt"].key, s3_deployment["endpoint"])
