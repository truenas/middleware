"""The deployment every S3 protocol module drives: accounts, buckets, a
running service, and the clients that reach it.

Session-scoped and shared: a module that writes keys under a prefix
drains it, and one that opens a multipart upload aborts it. Every bucket
is required, so a row that will not provision fails the session rather
than skipping its module.
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
from middlewared.test.integration.utils import call, pool, ssh
import pytest
from s3_client import client_for

#: Carried by every dataset and bucket this suite makes.
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

    Runs before anything this suite makes: it matches by prefix, so run
    later it would delete the session's own keys. Rows before datasets,
    because deregistering a bucket keeps its dataset.
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
    for row in call("zfs.resource.query", {"paths": [pool], "properties": None, "get_children": True}):
        if row["name"].startswith(f"{pool}/{PREFIX}-"):
            with contextlib.suppress(Exception):
                call("zfs.resource.destroy", {"path": row["name"], "recursive": True})


def _prove_signable(client, label: str) -> None:
    """Fail the session unless the S3 service holds this key. Judged on
    the credential codes alone: `alt` has nothing to list."""
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
    """The two licensed S3 features, entitled for the session. In force
    before the service starts: the daemon reads both at start-up."""
    with entitled("S3_VERSIONING"), entitled("S3_AUDIT"):
        yield


@pytest.fixture(scope="session")
def s3_accounts(s3_licensed, s3_clean_slate):
    """The two principals, and their keys.

    `main` holds `SHARING_S3_WRITE` and a grant on every bucket; its
    plain key lacks `manage_buckets` and `admin_key` carries it. `alt`
    holds no role and no grant: only a stored S3 ACL admits it.
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

    Order matters: buckets are made while the service is down, the
    excluded row's dataset is destroyed before the start, and the
    exported row's dataset exists before its row.
    """
    main = s3_accounts["main"]

    # the exported dataset: a few files, a child dataset mounted under
    # it, then read-only. `s3_bucket` destroys it on teardown.
    exported = dataset_for("exported")
    call("zfs.resource.create", {"path": f"{exported}/child", "create_ancestors": True})
    mount = f"/mnt/{exported}"
    ssh(
        f"mkdir -p {mount}/docs/2026 && printf alpha > {mount}/a.txt && printf bravo > {mount}/docs/2026/b.txt"
        f" && printf charlie > {mount}/child/c.txt && chmod -R a+rX {mount} && zfs set readonly=on {exported}"
    )

    # Every row grants `main` and nothing else.
    mine = [user_grant(main.uid)]
    rows = {
        # `OBJECT_WRITER` keeps the S3 ACL surface live for the ACL
        # modules; `COMPOSITE` because the multipart tests assert the
        # AWS form of the ETag.
        "attached": {
            "object_ownership": "OBJECT_WRITER",
            "owner": MAIN_USER,
            "grants": mine,
            "multipart_etag": "COMPOSITE",
        },
        # Versioned and locked, so nothing else may use it.
        "locked": {
            "object_ownership": "OBJECT_WRITER",
            "owner": MAIN_USER,
            "grants": mine,
            "versioning": "ENABLED",
            "object_lock": True,
        },
        # The same, with a default retention rule.
        "defaulted": {
            "object_ownership": "OBJECT_WRITER",
            "owner": MAIN_USER,
            "grants": mine,
            "versioning": "ENABLED",
            "object_lock": True,
            "object_lock_default_mode": "GOVERNANCE",
            "object_lock_default_days": 1,
        },
        # The snapshot layer: suspended, then never-versioned.
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
        "minted": {
            "object_ownership": "OBJECT_WRITER",
            "owner": MAIN_USER,
            "grants": mine,
            "multipart_etag": "MINTED",
        },
        # Owned by `alt` and written by `main`: a bucket whose owner is
        # its writer answers both ownership outcomes identically.
        "preferred": {
            "object_ownership": "BUCKET_OWNER_PREFERRED",
            "owner": ALT_USER,
            "grants": mine,
        },
        # A `DENY` grant naming the bucket's own owner.
        "denied": {
            "object_ownership": "OBJECT_WRITER",
            "owner": MAIN_USER,
            "grants": [user_grant(main.uid, "DENY")],
        },
        # Its dataset is destroyed below, so the daemon excludes it.
        "excluded": {"object_ownership": "OBJECT_WRITER", "owner": MAIN_USER, "grants": mine},
        # main owns it. Its tests check that the owner's own writes are refused.
        "exported": {"owner": MAIN_USER, "grants": mine, "layout": "DATASET"},
    }

    # Every row is required: a failure here fails the session.
    with contextlib.ExitStack() as stack:
        made = {
            leaf: stack.enter_context(s3_bucket(bucket_name(leaf), dataset=dataset_for(leaf), **options))
            for leaf, options in rows.items()
        }

        # Not `pool.dataset.delete`, which would deregister the bucket
        # with it: the row has to stand while its storage does not.
        call("zfs.resource.destroy", {"path": made["excluded"]["dataset"], "recursive": True})

        with s3_service():
            wait_for_listener(DEFAULT_S3_PORT)
            endpoint = s3_endpoint(DEFAULT_S3_PORT)

            # Checked here: per test, a missing key reads as an
            # authorization failure and passes every bare-403 case.
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
    """The same client with the SDK's default upload checksum turned off."""
    return client_for(
        s3_deployment["accounts"]["main"].key,
        s3_deployment["endpoint"],
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
    )


@pytest.fixture(scope="session")
def admin_s3(s3_deployment):
    """The same account as `s3`, on a key that carries `manage_buckets`."""
    return client_for(s3_deployment["accounts"]["main"].admin_key, s3_deployment["endpoint"])


@pytest.fixture
def wildcard_grant(accounts):
    """A grant over every bucket, for one case.

    Authorization answers before the engine or the grammar does, and
    `main` holds per-bucket rows only, so a case about what lies behind
    takes this. Restored on the way out: every other module depends on
    `main` reaching only what its own rows name.
    """
    was = call("s3.config")["global_grants"]
    call("s3.update", {"global_grants": [user_grant(accounts["main"].uid)]})
    try:
        yield
    finally:
        call("s3.update", {"global_grants": [{k: v for k, v in g.items() if k != "name"} for g in was]})


@pytest.fixture(scope="session")
def alt_s3(s3_deployment):
    """The second principal: authenticated, holding no grant anywhere."""
    return client_for(s3_deployment["accounts"]["alt"].key, s3_deployment["endpoint"])
