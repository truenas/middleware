"""The bucket namespace: what is listed, what is addressable, and what
every sub-resource probe answers.

A client's first act against a new endpoint is to probe the bucket — the
aws cli asks for `?location`, rclone and s3cmd ask for others, a console
asks for most of them — and each probe gets one of three answers here.
Which one is a deliberate choice per sub-resource rather than a default,
and the risk is not one wrong answer but a *reclassification*: a
sub-resource sliding from its own 404 to a generic one, or from an empty
200 to a 404, changes which branch every client takes, and no per-op
case sees the pattern.
"""

from middlewared.test.integration.assets.s3 import s3_endpoint
import pytest
from s3_client import code_in, code_of, raw_request, status_of

# ── the account listing ──────────────────────────────────────────────


def test_a_signed_call_passes_the_identity_layer(s3):
    """One signed call before anything else.

    Every failure below the identity layer looks identical from here — a
    wall of `AccessDenied` that says nothing about which of four things
    went wrong. `ListBuckets` gates on no bucket and no operation, so a
    refusal here is about *who the caller is*: the account cannot be
    resolved, PAM denies it, it is uid 0 (refused on purpose, so a
    credential cannot become root), or no grant covers it.
    """
    s3.list_buckets()


def test_the_listing_shows_what_serves_and_omits_what_does_not(s3, buckets):
    """An excluded row has no creation date to report.

    A bucket whose dataset never verified failed before its `statx` and
    never read one, so it is omitted from the listing even though
    addressing it answers 503 rather than 404 — the two facts are
    different and both are true at once.
    """
    rows = s3.list_buckets().get("Buckets", [])
    listed = [b["Name"] for b in rows]

    for name in (buckets["attached"], buckets["locked"]):
        assert name in listed, listed
        assert "CreationDate" in next(b for b in rows if b["Name"] == name)

    assert buckets["excluded"] not in listed, listed
    assert listed == sorted(listed), listed


def test_a_denied_bucket_leaves_the_listing_without_erroring_it(s3, buckets):
    """The kill switch must not take the account listing down.

    A `DENY` grant suspends the principal for that bucket alone, so the
    call succeeds, the served buckets are rows, and the denied one is
    filtered out per row rather than failing the whole listing.
    """
    denied = buckets["denied"]
    names = [b["Name"] for b in s3.list_buckets()["Buckets"]]
    assert buckets["attached"] in names
    assert denied not in names


def test_a_row_carries_its_region_and_the_filter_holds(s3):
    """`BucketRegion` rides every row; `bucket-region` filters on it."""
    rows = s3.list_buckets().get("Buckets", [])
    assert rows
    for row in rows:
        assert row.get("BucketRegion") == "us-east-1", row

    hit = s3.list_buckets(BucketRegion="us-east-1").get("Buckets", [])
    assert [b["Name"] for b in hit] == [b["Name"] for b in rows]
    assert s3.list_buckets(BucketRegion="eu-west-1").get("Buckets", []) == []


def test_an_unsigned_request_is_refused(daemon):
    """Credentials are the only way in, and a wrong signature is not a
    hint about what exists."""
    import boto3
    import botocore
    from botocore.config import Config

    anon = boto3.client(
        "s3",
        endpoint_url=daemon,
        verify=not daemon.startswith("https://"),
        config=Config(
            signature_version=botocore.UNSIGNED,
            s3={"addressing_style": "path"},
            retries={"max_attempts": 1},
        ),
    )
    with pytest.raises(botocore.exceptions.ClientError) as caught:
        anon.list_buckets()
    assert status_of(caught.value) == 403


# ── addressing one bucket ────────────────────────────────────────────


def test_an_attached_bucket_serves(s3, bucket):
    s3.head_bucket(Bucket=bucket)
    loc = s3.get_bucket_location(Bucket=bucket)
    # The deployment's default region renders as the *absent* constraint,
    # which is S3's own encoding of us-east-1 rather than the literal.
    assert loc.get("LocationConstraint") in (None, "")


def test_head_bucket_answers_its_region(s3, bucket):
    """`x-amz-bucket-region` on the 200 — the header SDKs discover a
    bucket's region by, matching what `?location` answers."""
    assert s3.head_bucket(Bucket=bucket)["BucketRegion"] == "us-east-1"


def test_a_failed_registration_is_unservable_not_absent(s3, buckets):
    """503, never 404.

    The row is addressable — it is configured — and unservable, because
    its dataset never verified. A 404 would say the bucket does not
    exist, which is a different fact and the one an operator would debug
    in the wrong place.
    """
    excluded = buckets["excluded"]
    with pytest.raises(Exception) as caught:
        s3.get_bucket_location(Bucket=excluded)
    assert status_of(caught.value) == 503
    assert code_of(caught.value) == "ServiceUnavailable"

    # HEAD carries no body, so only the status reaches the client.
    with pytest.raises(Exception) as caught:
        s3.head_bucket(Bucket=excluded)
    assert status_of(caught.value) == 503


@pytest.mark.parametrize("op", ["head_bucket", "get_bucket_location"])
def test_an_unconfigured_name_is_an_ordinary_404(s3, wildcard_grant, op):
    """A name nothing holds a row for, to a caller authorized for it.

    The wildcard grant is what makes this observable: authorization runs
    ahead of the engine, so without one the answer is the `403` below
    and the bucket's own condition is never reached.
    """
    with pytest.raises(Exception) as caught:
        getattr(s3, op)(Bucket="no-such-bucket-configured")
    assert status_of(caught.value) == 404


def test_a_name_the_caller_has_no_grant_for_hides_its_own_condition(s3, buckets):
    """`403` precedes existence, and three answers collapse into it.

    Authorization runs before the engine is consulted, so a caller with
    no grant for a name cannot tell an unconfigured bucket from an
    unservable one from a name that is not a bucket name at all — every
    one is the same bare `AccessDenied`. That is what stops error codes
    being used to map what a deployment holds.

    One case rather than three, because what matters is that they are
    *indistinguishable*, which no single parametrized run can show. Each
    is answered on its own merits elsewhere in this file, under
    `wildcard_grant`, where the caller is authorized for the name.
    """
    answers = {}
    for name, why in (
        ("no-such-bucket-configured", "nothing holds a row for it"),
        (buckets["excluded"], "a row stands and its storage does not"),
        ("a..b", "the grammar refuses the name outright"),
    ):
        with pytest.raises(Exception) as caught:
            s3.list_objects_v2(Bucket=name)
        answers[why] = (status_of(caught.value), code_of(caught.value))

    assert set(answers.values()) == {(403, "AccessDenied")}, answers


@pytest.mark.parametrize("op", ["create_bucket", "delete_bucket"])
def test_provisioning_without_the_flag_is_walled(s3, op):
    """403, not 501.

    A key without `manage_buckets` maps to no grantable action at all, so
    authorization walls these before any connector is consulted — the
    stronger answer of the two. A 501 would tell a prober the surface
    exists and is merely unbuilt; this says no principal may perform it.
    """
    with pytest.raises(Exception) as caught:
        getattr(s3, op)(Bucket="wire-made-bucket")
    assert status_of(caught.value) == 403


@pytest.mark.parametrize(
    "name",
    [
        "A",  # uppercase
        "a",  # under three characters
        "a" * 64,  # over sixty-three
        "a..b",  # adjacent periods
        "192.168.0.1",  # an address
        "-ab",  # leading hyphen
        "ab-",  # trailing hyphen
        "ab_c",  # underscore
    ],
)
def test_the_bucket_name_grammar_refuses(s3, wildcard_grant, name):
    """`InvalidBucketName`, and a 400 rather than a 404.

    A name the grammar refuses is answered before any lookup, so it
    cannot depend on whether a bucket of that name is configured — and it
    must not become `NoSuchBucket`, which tells a client to go and create
    one. Read over a listing rather than a `HEAD`, because HTTP gives a
    HEAD no body and an error code lives in the body.

    Under `wildcard_grant`, because authorization is answered first: a
    caller with no grant for the name gets the `403` above instead, and
    never reaches the grammar.
    """
    with pytest.raises(Exception) as caught:
        s3.list_objects_v2(Bucket=name)
    assert status_of(caught.value) == 400, name
    assert code_of(caught.value) == "InvalidBucketName", name


# ── the sub-resource matrix ──────────────────────────────────────────


def probe(s3, bucket, sub, method="GET"):
    """One signed `<method> /{bucket}?<sub>`, raw.

    Raw because half of these have no botocore model here, and a modeled
    call would report the SDK's opinion of an unknown element rather than
    the bytes.
    """
    return raw_request(s3, method, f"/{bucket}?{sub}")


#: Sub-resource -> the error code its absence answers with. Each is a
#: code S3 defines for that configuration alone, so a client can tell "no
#: lifecycle rules" from "no such bucket" without a second call.
ABSENT = {
    "replication": "ReplicationConfigurationNotFoundError",
    "encryption": "ServerSideEncryptionConfigurationNotFoundError",
    "website": "NoSuchWebsiteConfiguration",
    "cors": "NoSuchCORSConfiguration",
    "lifecycle": "NoSuchLifecycleConfiguration",
    "policy": "NoSuchBucketPolicy",
    "policyStatus": "NoSuchBucketPolicy",
    "tagging": "NoSuchTagSet",
    "object-lock": "ObjectLockConfigurationNotFoundError",
}

#: Sub-resource -> the root element of the empty document it answers. A
#: 404 here would be wrong: "no notifications configured" is the ordinary
#: state of a bucket, not a missing resource.
EMPTY = {
    "logging": "BucketLoggingStatus",
    "notification": "NotificationConfiguration",
    "accelerate": "AccelerateConfiguration",
    "requestPayment": "RequestPaymentConfiguration",
    "analytics": "ListBucketAnalyticsConfigurationResult",
    "intelligent-tiering": "ListBucketIntelligentTieringConfigurationsOutput",
    "inventory": "ListInventoryConfigurationsResult",
    "metrics": "ListMetricsConfigurationsResult",
}


@pytest.mark.parametrize("sub,code", sorted(ABSENT.items()))
def test_an_absent_configuration_answers_its_own_code(s3, bucket, sub, code):
    """404, and the code S3 defines for *this* sub-resource.

    The code is the assertion, not the status: every entry here is a 404,
    so a sub-resource answering the wrong one of these still looks right
    to any test that checked only the status.
    """
    resp = probe(s3, bucket, sub)
    assert resp.status_code == 404, f"?{sub} answered {resp.status_code}"
    assert code_in(resp.content) == code, f"?{sub}"


@pytest.mark.parametrize("sub,root", sorted(EMPTY.items()))
def test_an_unset_configuration_answers_an_empty_document(s3, bucket, sub, root):
    """200 with a well-formed empty document, not a refusal.

    A client that sees a 404 for `?notification` concludes the endpoint
    does not support notifications; one that sees an empty
    `<NotificationConfiguration/>` concludes there are none configured,
    which is the true thing.
    """
    resp = probe(s3, bucket, sub)
    assert resp.status_code == 200, f"?{sub} answered {resp.status_code}: {resp.content[:120]!r}"
    text = resp.content.decode("utf-8", "replace")
    assert text.startswith("<?xml "), f"?{sub} is not an XML document"
    assert root in text, f"?{sub} does not name <{root}>"
    assert "<Error>" not in text, f"?{sub} answered 200 with an error body"


def test_the_matrix_has_no_overlaps(s3, bucket):
    """A guard on the table above rather than on the server: a
    sub-resource listed in two classes would make one assertion
    unreachable while still passing."""
    names = list(ABSENT) + list(EMPTY)
    assert len(names) == len(set(names)), "a sub-resource is in two classes"
    assert ABSENT and EMPTY


def test_the_modeled_probes_answer_the_same_way(s3, bucket):
    """The probes a client runs through its SDK before it trusts a
    bucket. Each has to answer in the shape the SDK expects, not a bare
    error."""
    import botocore

    assert s3.get_bucket_location(Bucket=bucket) is not None

    for call, code in (
        ("get_bucket_policy", "NoSuchBucketPolicy"),
        ("get_bucket_tagging", "NoSuchTagSet"),
        ("get_bucket_cors", "NoSuchCORSConfiguration"),
        ("get_bucket_lifecycle_configuration", "NoSuchLifecycleConfiguration"),
        ("get_object_lock_configuration", "ObjectLockConfigurationNotFound"),
        ("get_bucket_replication", "ReplicationConfigurationNotFound"),
    ):
        with pytest.raises(botocore.exceptions.ClientError) as caught:
            getattr(s3, call)(Bucket=bucket)
        assert code_of(caught.value).startswith(code), f"{call}: {code_of(caught.value)}"

    # The probes AWS answers with a document rather than an absence. The
    # four list calls answer an empty *list*, which says no configuration
    # exists — not that one exists and is empty.
    for call, field in (
        ("list_bucket_analytics_configurations", "AnalyticsConfigurationList"),
        ("list_bucket_intelligent_tiering_configurations", "IntelligentTieringConfigurationList"),
        ("list_bucket_inventory_configurations", "InventoryConfigurationList"),
        ("list_bucket_metrics_configurations", "MetricsConfigurationList"),
    ):
        got = getattr(s3, call)(Bucket=bucket)
        assert got.get(field, []) == [], f"{call}: {got.get(field)}"
        assert got.get("IsTruncated") is False, call


# ── object sub-resources ─────────────────────────────────────────────


#: Object sub-resources answered `NotImplemented`, whatever the method.
#: `select` is POST-only at AWS and `torrent` GET-only; the answer here
#: does not vary by method, which is what the parametrization asserts.
UNIMPLEMENTED = ["attributes", "policyStatus", "restore", "select", "torrent"]

#: `HEAD` is left out: HTTP gives it no body, and the code lives in one.
METHODS = ["GET", "PUT", "POST", "DELETE"]


@pytest.fixture(scope="module")
def probe_object(s3, bucket):
    """A real object, so a 501 cannot be a 404 wearing a costume."""
    key = "subres/object.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"body")
    return key


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("sub", UNIMPLEMENTED)
def test_an_unimplemented_object_subresource_is_501(s3, bucket, probe_object, sub, method):
    """`NotImplemented`, with the sub-resource named in the message.

    **Falling through is the failure worth naming.** `PUT
    /{bucket}/{key}` is a write, and `?restore` is one query parameter
    away from it — a router that ignored an unknown sub-resource would
    answer `200` and store a restore request *as the object*.
    """
    resp = raw_request(
        s3,
        method,
        f"/{bucket}/{probe_object}?{sub}",
        body=b"" if method in ("PUT", "POST") else None,
    )
    assert resp.status_code == 501, f"{method} ?{sub}"
    assert b"NotImplemented" in resp.content, f"{method} ?{sub}"
    assert sub.encode() in resp.content, f"{method} ?{sub} names no surface"


def test_the_object_is_untouched_by_every_probe(s3, bucket, probe_object):
    """The assertion the status codes cannot make.

    A `PUT ?restore` that answered 501 *after* writing the body would
    look identical from the outside, and it is the one failure this
    matrix exists to catch.
    """
    got = s3.get_object(Bucket=bucket, Key=probe_object)
    assert got["Body"].read() == b"body"
    assert got["ContentLength"] == 4


def test_a_bucket_only_subresource_on_a_key_is_not_the_key(s3, bucket, probe_object):
    """`?versions` names a bucket listing, so on a key it is a 501 and
    never the object.

    The sub-resource is implemented — at the level above. A router that
    matched on the name alone would either run a version listing rooted
    at a key or serve the object and ignore the parameter, and both are
    silent.
    """
    resp = raw_request(s3, "GET", f"/{bucket}/{probe_object}?versions")
    assert resp.status_code == 501
    assert b"versions" in resp.content


def test_the_endpoint_is_the_server_under_test(daemon):
    """A guard on the fixtures rather than on the server.

    Everything above is meaningless if the client is pointed somewhere
    else, and an endpoint built from the wrong address fails as a
    connection error whose message names no bucket.
    """
    assert daemon == s3_endpoint()
