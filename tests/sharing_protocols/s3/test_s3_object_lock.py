"""Object Lock: retention, legal hold, and the gate both stand behind.

The locked bucket is the session's `versioning = ENABLED` +
`object_lock = True` row — a latch middleware asks for at creation and
the daemon stamps on the dataset root at registration, which never
lowers. The unlocked half runs against the ordinary bucket, because the
gate is exactly that both spellings — the create headers and the
operations — are refused there.

The caller is the bucket's owner, which is what authorizes the
governance bypass: no grant mode carries it, and the owner reaches it
through the evaluator's ownership rule. Dates are fixed and far future;
nothing here reads the wall clock closer than "not yet".
"""

import datetime

import pytest
from s3_client import code_of, status_of

UNTIL = datetime.datetime(2035, 1, 1, tzinfo=datetime.timezone.utc)
LATER = datetime.datetime(2036, 1, 1, tzinfo=datetime.timezone.utc)
EARLIER = datetime.datetime(2034, 1, 1, tzinfo=datetime.timezone.utc)


@pytest.fixture(scope="module")
def locked(buckets):
    name = buckets.get("locked")
    if not name:
        pytest.skip("no locked bucket: the session could not provision one")
    return name


@pytest.fixture(scope="module")
def defaulted(buckets):
    name = buckets.get("defaulted")
    if not name:
        pytest.skip("no default-rule bucket: the session could not provision one")
    return name


def put_locked(s3, bucket, key, mode, until=UNTIL):
    return s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=b"held",
        ObjectLockMode=mode,
        ObjectLockRetainUntilDate=until,
    )


# ── the bucket gate ──────────────────────────────────────────────────


def test_the_configuration_reads_enabled(s3, locked):
    cfg = s3.get_object_lock_configuration(Bucket=locked)["ObjectLockConfiguration"]
    assert cfg["ObjectLockEnabled"] == "Enabled"
    assert "Rule" not in cfg, "this row carries no default rule"


def test_an_unlocked_bucket_has_no_configuration(s3, bucket):
    with pytest.raises(Exception) as caught:
        s3.get_object_lock_configuration(Bucket=bucket)
    assert status_of(caught.value) == 404
    assert code_of(caught.value) == "ObjectLockConfigurationNotFoundError"


def test_lock_headers_on_an_unlocked_bucket_are_refused(s3, bucket):
    with pytest.raises(Exception) as caught:
        put_locked(s3, bucket, "lock/refused.bin", "COMPLIANCE")
    assert status_of(caught.value) == 400
    assert code_of(caught.value) == "InvalidRequest"


def test_retention_operations_on_an_unlocked_bucket_are_refused(s3, bucket):
    """AWS gates all four operations on the configuration, reads
    included — so the read is asserted beside the write."""
    s3.put_object(Bucket=bucket, Key="lock/plain.bin", Body=b"x")

    with pytest.raises(Exception) as caught:
        s3.put_object_retention(
            Bucket=bucket,
            Key="lock/plain.bin",
            Retention={"Mode": "GOVERNANCE", "RetainUntilDate": UNTIL},
        )
    assert code_of(caught.value) == "InvalidRequest"

    with pytest.raises(Exception) as caught:
        s3.get_object_retention(Bucket=bucket, Key="lock/plain.bin")
    assert status_of(caught.value) == 400
    assert code_of(caught.value) == "InvalidRequest"


# ── the stamp ────────────────────────────────────────────────────────


def test_a_create_stamp_reads_back_everywhere(s3, locked):
    """The header pair stores, and every read reports it."""
    vid = put_locked(s3, locked, "lock/stamp.bin", "COMPLIANCE")["VersionId"]

    head = s3.head_object(Bucket=locked, Key="lock/stamp.bin")
    assert head["ObjectLockMode"] == "COMPLIANCE"
    assert head["ObjectLockRetainUntilDate"] == UNTIL
    assert "ObjectLockLegalHoldStatus" not in head, "never held is absent"

    got = s3.get_object_retention(Bucket=locked, Key="lock/stamp.bin", VersionId=vid)
    assert got["Retention"]["Mode"] == "COMPLIANCE"
    assert got["Retention"]["RetainUntilDate"] == UNTIL


def test_a_create_time_legal_hold_lands_and_holds(s3, locked):
    """boto3 spells the wire header from the `ObjectLockLegalHoldStatus`
    member, so this case fails against any parser reading the member name
    off the wire."""
    key = "lock/born-held.bin"
    vid = s3.put_object(Bucket=locked, Key=key, Body=b"held", ObjectLockLegalHoldStatus="ON")["VersionId"]
    assert s3.head_object(Bucket=locked, Key=key).get("ObjectLockLegalHoldStatus") == "ON"
    assert s3.get_object_legal_hold(Bucket=locked, Key=key, VersionId=vid)["LegalHold"]["Status"] == "ON"

    with pytest.raises(Exception) as caught:
        s3.delete_object(Bucket=locked, Key=key, VersionId=vid)
    assert status_of(caught.value) == 403

    s3.put_object_legal_hold(Bucket=locked, Key=key, VersionId=vid, LegalHold={"Status": "OFF"})
    s3.delete_object(Bucket=locked, Key=key, VersionId=vid)


def test_multipart_carries_the_create_pair(s3, locked):
    """The pair named at `CreateMultipartUpload` rides to the completed
    object — the path a client actually uses for immutable uploads."""
    key = "lock/assembled.bin"
    uid = s3.create_multipart_upload(
        Bucket=locked, Key=key, ObjectLockMode="COMPLIANCE", ObjectLockRetainUntilDate=UNTIL
    )["UploadId"]
    part = s3.upload_part(Bucket=locked, Key=key, UploadId=uid, PartNumber=1, Body=b"z" * (5 * 1024 * 1024))
    done = s3.complete_multipart_upload(
        Bucket=locked,
        Key=key,
        UploadId=uid,
        MultipartUpload={"Parts": [{"ETag": part["ETag"], "PartNumber": 1}]},
    )
    got = s3.get_object_retention(Bucket=locked, Key=key, VersionId=done["VersionId"])
    assert got["Retention"]["Mode"] == "COMPLIANCE"
    assert got["Retention"]["RetainUntilDate"] == UNTIL


def test_a_copy_carries_its_own_retention_never_the_sources(s3, locked):
    """Retention is per version and a copy is a new one: the request's
    pair rides, the source's never does."""
    src = "lock/copy-src.bin"
    put_locked(s3, locked, src, "GOVERNANCE")

    plain = s3.copy_object(Bucket=locked, Key="lock/copy-plain.bin", CopySource={"Bucket": locked, "Key": src})
    with pytest.raises(Exception) as caught:
        s3.get_object_retention(Bucket=locked, Key="lock/copy-plain.bin", VersionId=plain["VersionId"])
    assert code_of(caught.value) == "NoSuchObjectLockConfiguration"

    stamped = s3.copy_object(
        Bucket=locked,
        Key="lock/copy-stamped.bin",
        CopySource={"Bucket": locked, "Key": src},
        ObjectLockMode="COMPLIANCE",
        ObjectLockRetainUntilDate=UNTIL,
    )
    got = s3.get_object_retention(Bucket=locked, Key="lock/copy-stamped.bin", VersionId=stamped["VersionId"])
    assert got["Retention"]["Mode"] == "COMPLIANCE"


# ── what retention refuses ───────────────────────────────────────────


def test_compliance_extends_and_never_shortens(s3, locked):
    vid = put_locked(s3, locked, "lock/extend.bin", "COMPLIANCE")["VersionId"]
    target = {"Bucket": locked, "Key": "lock/extend.bin", "VersionId": vid}

    s3.put_object_retention(Retention={"Mode": "COMPLIANCE", "RetainUntilDate": LATER}, **target)
    assert s3.get_object_retention(**target)["Retention"]["RetainUntilDate"] == LATER

    for retention in (
        {"Mode": "COMPLIANCE", "RetainUntilDate": EARLIER},
        {"Mode": "GOVERNANCE", "RetainUntilDate": LATER},
    ):
        with pytest.raises(Exception) as caught:
            s3.put_object_retention(Retention=retention, BypassGovernanceRetention=True, **target)
        assert code_of(caught.value) == "AccessDenied", retention


@pytest.mark.parametrize("bypass", [False, True])
def test_compliance_refuses_deletion_through_any_bypass(s3, locked, bypass):
    vid = put_locked(s3, locked, "lock/keep.bin", "COMPLIANCE")["VersionId"]
    with pytest.raises(Exception) as caught:
        s3.delete_object(Bucket=locked, Key="lock/keep.bin", VersionId=vid, BypassGovernanceRetention=bypass)
    assert status_of(caught.value) == 403, f"bypass={bypass}"


def test_the_unversioned_delete_of_a_retained_key_still_marks(s3, locked):
    """Retention refuses destruction of a *version*, never the delete of
    a key: the bare DELETE answers a marker as it would anywhere."""
    put_locked(s3, locked, "lock/marked-key.bin", "COMPLIANCE")
    assert s3.delete_object(Bucket=locked, Key="lock/marked-key.bin")["DeleteMarker"] is True


def test_governance_yields_to_the_owners_bypass(s3, locked):
    vid = put_locked(s3, locked, "lock/soft.bin", "GOVERNANCE")["VersionId"]
    with pytest.raises(Exception) as caught:
        s3.delete_object(Bucket=locked, Key="lock/soft.bin", VersionId=vid)
    assert status_of(caught.value) == 403

    s3.delete_object(Bucket=locked, Key="lock/soft.bin", VersionId=vid, BypassGovernanceRetention=True)
    listed = s3.list_object_versions(Bucket=locked, Prefix="lock/soft.bin")
    assert vid not in [v["VersionId"] for v in listed.get("Versions", [])]


def test_a_mode_change_needs_the_bypass(s3, locked):
    """GOVERNANCE converts to COMPLIANCE only under the bypass, and
    extends freely within its own mode."""
    key = "lock/modes.bin"
    s3.put_object(
        Bucket=locked,
        Key=key,
        Body=b"m",
        ObjectLockMode="GOVERNANCE",
        ObjectLockRetainUntilDate=UNTIL,
    )
    with pytest.raises(Exception) as caught:
        s3.put_object_retention(Bucket=locked, Key=key, Retention={"Mode": "COMPLIANCE", "RetainUntilDate": UNTIL})
    assert status_of(caught.value) == 403

    s3.put_object_retention(
        Bucket=locked,
        Key=key,
        Retention={"Mode": "COMPLIANCE", "RetainUntilDate": UNTIL},
        BypassGovernanceRetention=True,
    )
    assert s3.get_object_retention(Bucket=locked, Key=key)["Retention"]["Mode"] == "COMPLIANCE"


def test_a_governance_clear_needs_the_bypass(s3, locked):
    """An empty `<Retention/>` is the clear, and clearing weakens."""
    key = "lock/cleared.bin"
    vid = put_locked(s3, locked, key, "GOVERNANCE")["VersionId"]
    target = {"Bucket": locked, "Key": key, "VersionId": vid}

    with pytest.raises(Exception) as caught:
        s3.put_object_retention(Retention={}, **target)
    assert code_of(caught.value) == "AccessDenied"

    s3.put_object_retention(Retention={}, BypassGovernanceRetention=True, **target)
    with pytest.raises(Exception) as caught:
        s3.get_object_retention(**target)
    assert code_of(caught.value) == "NoSuchObjectLockConfiguration"

    # Unretained now, the version deletes without any bypass.
    s3.delete_object(**target)


def test_a_legal_hold_is_dateless_and_tristate(s3, locked):
    key = "lock/hold.bin"
    vid = put_locked(s3, locked, key, "GOVERNANCE")["VersionId"]
    target = {"Bucket": locked, "Key": key, "VersionId": vid}

    # Never applied answers absence, not OFF.
    with pytest.raises(Exception) as caught:
        s3.get_object_legal_hold(**target)
    assert status_of(caught.value) == 400
    assert code_of(caught.value) == "NoSuchObjectLockConfiguration"

    s3.put_object_legal_hold(LegalHold={"Status": "ON"}, **target)
    assert s3.get_object_legal_hold(**target)["LegalHold"]["Status"] == "ON"

    # Held refuses destruction whatever the mode or bypass says.
    with pytest.raises(Exception) as caught:
        s3.delete_object(BypassGovernanceRetention=True, **target)
    assert status_of(caught.value) == 403

    s3.put_object_legal_hold(LegalHold={"Status": "OFF"}, **target)
    assert s3.get_object_legal_hold(**target)["LegalHold"]["Status"] == "OFF"
    s3.delete_object(BypassGovernanceRetention=True, **target)


def test_an_overwrite_of_a_locked_key_is_a_new_version(s3, locked):
    """A PUT to a protected key answers 200 and a new version: retention
    refuses destruction, never writes.

    The demotion arms the fence on the superseded version, and both its
    readability and its refusal must survive it. Some gateways refuse the
    overwrite outright; AWS demotes, and so does this server.
    """
    key = "lock/generations.bin"
    old = put_locked(s3, locked, key, "COMPLIANCE")["VersionId"]
    new = s3.put_object(Bucket=locked, Key=key, Body=b"newer")["VersionId"]
    assert new != old

    assert s3.get_object(Bucket=locked, Key=key, VersionId=old)["Body"].read() == b"held"
    with pytest.raises(Exception) as caught:
        s3.delete_object(Bucket=locked, Key=key, VersionId=old, BypassGovernanceRetention=True)
    assert status_of(caught.value) == 403, "and still refuses destruction"


def test_a_marker_takes_no_retention(s3, locked):
    put_locked(s3, locked, "lock/marked.bin", "GOVERNANCE")
    marker = s3.delete_object(Bucket=locked, Key="lock/marked.bin")["VersionId"]
    with pytest.raises(Exception) as caught:
        s3.put_object_retention(
            Bucket=locked,
            Key="lock/marked.bin",
            VersionId=marker,
            Retention={"Mode": "GOVERNANCE", "RetainUntilDate": UNTIL},
        )
    assert status_of(caught.value) == 405


def test_a_retention_date_in_the_past_is_refused(s3, locked):
    """A version born expired is a version that was never protected."""
    past = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    with pytest.raises(Exception) as caught:
        put_locked(s3, locked, "lock/past.bin", "GOVERNANCE", past)
    assert code_of(caught.value) == "InvalidArgument"


def test_retention_operations_on_absent_targets(s3, locked):
    """The family 404s an absent key before any lock state is consulted,
    and a well-formed id naming nothing is `NoSuchVersion`."""
    with pytest.raises(Exception) as caught:
        s3.get_object_retention(Bucket=locked, Key="lock/absent.bin")
    assert code_of(caught.value) == "NoSuchKey"

    with pytest.raises(Exception) as caught:
        s3.put_object_legal_hold(Bucket=locked, Key="lock/absent.bin", LegalHold={"Status": "ON"})
    assert code_of(caught.value) == "NoSuchKey"

    vid = put_locked(s3, locked, "lock/present.bin", "GOVERNANCE")["VersionId"]
    ghost = ("0" * 31) + ("1" if vid[-1] != "1" else "2")
    with pytest.raises(Exception) as caught:
        s3.get_object_retention(Bucket=locked, Key="lock/present.bin", VersionId=ghost)
    assert code_of(caught.value) == "NoSuchVersion"


def test_a_value_outside_the_enum_is_a_malformed_document(s3, locked):
    put_locked(s3, locked, "lock/body.bin", "GOVERNANCE")
    with pytest.raises(Exception) as caught:
        s3.put_object_retention(
            Bucket=locked,
            Key="lock/body.bin",
            Retention={"Mode": "governance", "RetainUntilDate": LATER},
        )
    assert code_of(caught.value) == "MalformedXML"

    with pytest.raises(Exception) as caught:
        s3.put_object_legal_hold(Bucket=locked, Key="lock/body.bin", LegalHold={"Status": "on"})
    assert code_of(caught.value) == "MalformedXML"


def test_a_batch_delete_reports_retention_per_row(s3, locked):
    """A manifest mixing protected and plain rows answers 200 with the
    refusal as that row's error, never a whole-request 403."""
    held = put_locked(s3, locked, "lock/batch-held.bin", "COMPLIANCE")["VersionId"]
    plain = s3.put_object(Bucket=locked, Key="lock/batch-plain.bin", Body=b"x")["VersionId"]

    out = s3.delete_objects(
        Bucket=locked,
        Delete={
            "Objects": [
                {"Key": "lock/batch-held.bin", "VersionId": held},
                {"Key": "lock/batch-plain.bin", "VersionId": plain},
            ],
            "Quiet": False,
        },
    )
    assert {e["Key"]: e["Code"] for e in out.get("Errors", [])} == {"lock/batch-held.bin": "AccessDenied"}
    assert "lock/batch-plain.bin" in {d["Key"] for d in out.get("Deleted", [])}


# ── the bucket's default rule ────────────────────────────────────────


def test_a_silent_create_inherits_the_rule(s3, defaulted):
    """`object_lock_default_mode` and `object_lock_default_days` are
    middleware's fields, and this is where they become an object's."""
    s3.put_object(Bucket=defaulted, Key="dft/quiet.bin", Body=b"q")
    head = s3.head_object(Bucket=defaulted, Key="dft/quiet.bin")
    assert head["ObjectLockMode"] == "GOVERNANCE"

    left = (head["ObjectLockRetainUntilDate"] - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    # One configured day, minus the seconds this took, plus clock slack.
    assert 12 * 3600 < left <= 24 * 3600 + 300, left


def test_an_explicit_pair_overrides_the_rule(s3, defaulted):
    s3.put_object(
        Bucket=defaulted,
        Key="dft/loud.bin",
        Body=b"q",
        ObjectLockMode="COMPLIANCE",
        ObjectLockRetainUntilDate=UNTIL,
    )
    head = s3.head_object(Bucket=defaulted, Key="dft/loud.bin")
    assert head["ObjectLockMode"] == "COMPLIANCE"
    assert head["ObjectLockRetainUntilDate"] == UNTIL


def test_the_configuration_reports_the_rule(s3, defaulted):
    cfg = s3.get_object_lock_configuration(Bucket=defaulted)["ObjectLockConfiguration"]
    assert cfg["ObjectLockEnabled"] == "Enabled"
    assert cfg["Rule"]["DefaultRetention"] == {"Mode": "GOVERNANCE", "Days": 1}


def test_the_inherited_stamp_is_governance_in_fact(s3, defaulted):
    """Proven by its semantics rather than by reading it back: the plain
    destroy refuses and the owner's bypass destroys."""
    s3.put_object(Bucket=defaulted, Key="dft/held.bin", Body=b"q")
    vid = s3.head_object(Bucket=defaulted, Key="dft/held.bin")["VersionId"]

    with pytest.raises(Exception) as caught:
        s3.delete_object(Bucket=defaulted, Key="dft/held.bin", VersionId=vid)
    assert code_of(caught.value) == "AccessDenied"

    s3.delete_object(Bucket=defaulted, Key="dft/held.bin", VersionId=vid, BypassGovernanceRetention=True)
