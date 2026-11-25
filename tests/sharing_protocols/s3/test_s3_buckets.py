"""The bucket namespace: what is listed, what is addressable, and what
each sub-resource probe answers."""

import json

from middlewared.test.integration.assets.s3 import s3_endpoint
import pytest
from s3_client import code_in, code_of, raw_request, status_of

# ── the account listing ──────────────────────────────────────────────


def test_a_signed_call_passes_the_identity_layer(s3):
    """`ListBuckets` gates on no bucket, so a refusal here is about the
    caller: unresolvable, denied by PAM, uid 0, or under no grant."""
    s3.list_buckets()


def test_the_listing_shows_what_serves_and_omits_what_does_not(s3, buckets):
    """An excluded row is left out of the listing, though it answers 503."""
    rows = s3.list_buckets().get("Buckets", [])
    listed = [b["Name"] for b in rows]

    for name in (buckets["attached"], buckets["locked"]):
        assert name in listed, listed
        assert "CreationDate" in next(b for b in rows if b["Name"] == name)

    assert buckets["excluded"] not in listed, listed
    assert listed == sorted(listed), listed


def test_a_denied_bucket_leaves_the_listing_without_erroring_it(s3, buckets):
    """A `DENY` filters its own row out and the listing still succeeds."""
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
    # us-east-1 renders as the absent constraint, S3's own encoding.
    assert loc.get("LocationConstraint") in (None, "")


def test_head_bucket_answers_its_region(s3, bucket):
    """`x-amz-bucket-region` on the 200, matching `?location`."""
    assert s3.head_bucket(Bucket=bucket)["BucketRegion"] == "us-east-1"


def test_a_failed_registration_is_unservable_not_absent(s3, buckets):
    """503, never 404: the row is configured and its dataset is gone."""
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
    """Under `wildcard_grant`, so the `404` is the engine's own."""
    with pytest.raises(Exception) as caught:
        getattr(s3, op)(Bucket="no-such-bucket-configured")
    assert status_of(caught.value) == 404


def test_a_name_no_row_holds_is_absent_to_any_signed_caller(s3, alt_s3):
    """`404 NoSuchBucket` with no grant reaching the name. A name the
    grammar refuses answers the same: the grammar is never reached."""
    answers = {}
    for who, client, name in (
        ("main", s3, "no-such-bucket-configured"),
        ("alt", alt_s3, "no-such-bucket-configured"),
        ("main", s3, "a..b"),
    ):
        with pytest.raises(Exception) as caught:
            client.list_objects_v2(Bucket=name)
        answers[who, name] = (status_of(caught.value), code_of(caught.value))

    assert set(answers.values()) == {(404, "NoSuchBucket")}, answers


def test_a_refusal_says_the_name_is_taken_and_nothing_else(s3, alt_s3, buckets):
    """The bare `403` wherever a row stands, serving or not. `main`
    holds a row on the excluded bucket and is told `503` instead."""
    answers = {}
    for who, client, name, why in (
        ("alt", alt_s3, buckets["denied"], "a row that stands and serves"),
        ("alt", alt_s3, buckets["excluded"], "a row that stands and will not serve"),
        ("main", s3, buckets["denied"], "a row that stands and serves, refused by a DENY"),
    ):
        with pytest.raises(Exception) as caught:
            client.list_objects_v2(Bucket=name)
        answers[who, why] = (status_of(caught.value), code_of(caught.value))

    assert set(answers.values()) == {(403, "AccessDenied")}, answers


@pytest.mark.parametrize("op", ["create_bucket", "delete_bucket"])
def test_provisioning_without_the_flag_is_walled(s3, op):
    """403, not 501, and not the `404` above: a key without
    `manage_buckets` is refused before any name is read."""
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
    """`400 InvalidBucketName`, read over a listing because a HEAD has
    no body. Under `wildcard_grant`: with no grant reaching the name,
    authorization answers `404 NoSuchBucket` before the grammar."""
    with pytest.raises(Exception) as caught:
        s3.list_objects_v2(Bucket=name)
    assert status_of(caught.value) == 400, name
    assert code_of(caught.value) == "InvalidBucketName", name


# ── the sub-resource matrix ──────────────────────────────────────────


def probe(s3, bucket, sub, method="GET"):
    """One signed `<method> /{bucket}?<sub>`, raw: half have no botocore model."""
    return raw_request(s3, method, f"/{bucket}?{sub}")


#: Sub-resource -> the error code its absence answers with.
ABSENT = {
    "replication": "ReplicationConfigurationNotFoundError",
    "encryption": "ServerSideEncryptionConfigurationNotFoundError",
    "website": "NoSuchWebsiteConfiguration",
    "cors": "NoSuchCORSConfiguration",
    "lifecycle": "NoSuchLifecycleConfiguration",
    "tagging": "NoSuchTagSet",
    "object-lock": "ObjectLockConfigurationNotFoundError",
}

#: Sub-resource -> the root element of the empty document it answers.
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

#: The policy is the bucket's grant rows: a document where a row names
#: the bucket, `NoSuchBucketPolicy` where none does (`test_s3_grants.py`).
POLICY = ["policy", "policyStatus"]


@pytest.mark.parametrize("sub,code", sorted(ABSENT.items()))
def test_an_absent_configuration_answers_its_own_code(s3, bucket, sub, code):
    """404, and the code S3 defines for this sub-resource."""
    resp = probe(s3, bucket, sub)
    assert resp.status_code == 404, f"?{sub} answered {resp.status_code}"
    assert code_in(resp.content) == code, f"?{sub}"


@pytest.mark.parametrize("sub,root", sorted(EMPTY.items()))
def test_an_unset_configuration_answers_an_empty_document(s3, bucket, sub, root):
    """200 with a well-formed empty document, not a refusal."""
    resp = probe(s3, bucket, sub)
    assert resp.status_code == 200, f"?{sub} answered {resp.status_code}: {resp.content[:120]!r}"
    text = resp.content.decode("utf-8", "replace")
    assert text.startswith("<?xml "), f"?{sub} is not an XML document"
    assert root in text, f"?{sub} does not name <{root}>"
    assert "<Error>" not in text, f"?{sub} answered 200 with an error body"


def test_the_policy_probes_answer_for_the_grant_rows(s3, bucket, accounts):
    """One statement per grant row, and this bucket carries one."""
    main = accounts["main"]

    resp = probe(s3, bucket, "policy")
    assert resp.status_code == 200, f"?policy answered {resp.status_code}: {resp.content[:120]!r}"
    [statement] = json.loads(resp.content)["Statement"]
    assert statement["Effect"] == "Allow"
    assert statement["Principal"] == {"AWS": f"arn:aws:iam::{main.uid}:user/{main.username}"}
    assert statement["Resource"] == [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"]
    assert {"s3:GetObject", "s3:PutObject", "s3:ListBucket"} <= set(statement["Action"]), statement["Action"]

    resp = probe(s3, bucket, "policyStatus")
    assert resp.status_code == 200, f"?policyStatus answered {resp.status_code}: {resp.content[:120]!r}"
    assert b"<IsPublic>false</IsPublic>" in resp.content, resp.content


def test_the_matrix_has_no_overlaps(s3, bucket):
    """A guard on the tables above: no sub-resource in two classes."""
    names = list(ABSENT) + list(EMPTY) + POLICY
    assert len(names) == len(set(names)), "a sub-resource is in two classes"
    assert ABSENT and EMPTY


def test_the_modeled_probes_answer_the_same_way(s3, bucket):
    """The same probes through the SDK's modeled calls."""
    import botocore

    assert s3.get_bucket_location(Bucket=bucket) is not None

    for call, code in (
        ("get_bucket_tagging", "NoSuchTagSet"),
        ("get_bucket_cors", "NoSuchCORSConfiguration"),
        ("get_bucket_lifecycle_configuration", "NoSuchLifecycleConfiguration"),
        ("get_object_lock_configuration", "ObjectLockConfigurationNotFound"),
        ("get_bucket_replication", "ReplicationConfigurationNotFound"),
    ):
        with pytest.raises(botocore.exceptions.ClientError) as caught:
            getattr(s3, call)(Bucket=bucket)
        assert code_of(caught.value).startswith(code), f"{call}: {code_of(caught.value)}"

    # The policy pair answers for the grant row this bucket carries.
    assert json.loads(s3.get_bucket_policy(Bucket=bucket)["Policy"])["Statement"]
    assert s3.get_bucket_policy_status(Bucket=bucket)["PolicyStatus"]["IsPublic"] is False

    # These answer an empty list rather than an absence.
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
UNIMPLEMENTED = ["attributes", "policyStatus", "restore", "select", "torrent"]

#: `HEAD` is left out: HTTP gives it no body, and the code lives in one.
METHODS = ["GET", "PUT", "POST", "DELETE"]


@pytest.fixture(scope="module")
def probe_object(s3, bucket):
    """A real object, so a 501 is not a 404."""
    key = "subres/object.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"body")
    return key


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("sub", UNIMPLEMENTED)
def test_an_unimplemented_object_subresource_is_501(s3, bucket, probe_object, sub, method):
    """`NotImplemented`, naming the sub-resource. A `PUT` that fell
    through would store the request as the object."""
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
    """A `PUT ?restore` that wrote before answering 501 would look the same."""
    got = s3.get_object(Bucket=bucket, Key=probe_object)
    assert got["Body"].read() == b"body"
    assert got["ContentLength"] == 4


def test_a_bucket_only_subresource_on_a_key_is_not_the_key(s3, bucket, probe_object):
    """`?versions` on a key is a 501, never the object."""
    resp = raw_request(s3, "GET", f"/{bucket}/{probe_object}?versions")
    assert resp.status_code == 501
    assert b"versions" in resp.content


def test_the_endpoint_is_the_server_under_test(daemon):
    """A guard on the fixtures: the client points at the server under test."""
    assert daemon == s3_endpoint()
