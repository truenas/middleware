"""The S3 client stack: boto3, and the helpers a protocol case needs.

The split from `middlewared.test.integration.assets.s3` is the one
`nfs_proto` and `smb_proto` draw against their own assets. The **asset**
module provisions — accounts, access keys, buckets, grants, the
service — and is pure middleware API, so it imports nothing a client
stack brings with it. What is here is the other side of the wire: the
signed client, the helpers that read an answer off it, and the two
request shapes botocore will not construct.

**In this directory rather than in `tests/protocols/`**, which is where
the other protocol clients live. That package's `__init__` imports every
client it re-exports, so a module under it would make an S3 case need
samba, pynfs and pyscsi installed to reach boto3. Imported by bare name,
as `nfs/` and `nvmet/` import their own helper modules.

`boto3` is imported inside the functions that use it, so importing this
module costs nothing on a runner without it.
"""

import hashlib
import os
from typing import Any

from middlewared.test.integration.assets.s3 import s3_endpoint

__all__ = [
    "ALL_USERS",
    "AUTHENTICATED_USERS",
    "CHUNK",
    "SIZES",
    "RawResponse",
    "client_for",
    "code_in",
    "code_of",
    "digest",
    "drain",
    "grants_of",
    "md5_of",
    "payload",
    "random_file",
    "raw_query",
    "raw_request",
    "s3_client",
    "status_of",
]

CHUNK = 1024 * 1024
SIZES = [0, 1, 4096, CHUNK - 1, CHUNK, CHUNK + 1, 5 * CHUNK]
"""The write sizes a round trip covers: empty, one byte, a page, and the
three that straddle the daemon's buffered cap."""

ALL_USERS = "http://acs.amazonaws.com/groups/global/AllUsers"
AUTHENTICATED_USERS = "http://acs.amazonaws.com/groups/global/AuthenticatedUsers"
"""The two ACL group URIs, spelled as AWS spells them."""


# ── the client ───────────────────────────────────────────────────────


def s3_client(endpoint: str | None = None, *, access_key: str, secret_key: str, **config):
    """A boto3 client for the S3 service under test.

    Path addressing because the endpoint is an IP, and one attempt per
    call so a refusal under test is one request and one answer rather
    than four. Verification is off under TLS: the certificate a test
    mints is self-signed, and what a TLS case proves is the handshake
    and not a trust chain.

    The checksum stance is stated rather than inherited from whichever
    botocore the runner has: modern versions send `x-amz-checksum-crc32`
    on every upload and validate it on every read, which is what the
    daemon serves, and a runner whose default differed would change what
    half the suite is testing.
    """
    import boto3
    from botocore.config import Config

    endpoint = endpoint or s3_endpoint()
    settings = {
        "signature_version": "s3v4",
        "s3": {"addressing_style": "path"},
        "retries": {"max_attempts": 1, "mode": "standard"},
        "request_checksum_calculation": "when_supported",
        "response_checksum_validation": "when_supported",
    }
    settings.update(config)
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        verify=not endpoint.startswith("https://"),
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
        config=Config(**settings),
    )


def client_for(key: dict[str, Any], endpoint: str | None = None, **config):
    """A client signing with the pair an `s3.accesskey` entry carries."""
    return s3_client(endpoint, access_key=key["access_key"], secret_key=key["secret"], **config)


# ── reading an answer ────────────────────────────────────────────────


def status_of(err) -> int:
    """The HTTP status a botocore `ClientError` carries."""
    return err.response["ResponseMetadata"]["HTTPStatusCode"]


def code_of(err) -> str:
    """The `<Code>` a botocore `ClientError` carries."""
    return err.response["Error"]["Code"]


def grants_of(doc: dict[str, Any]) -> list[tuple[str, str]]:
    """The (grantee, permission) rows of an ACL document, in order.

    Grantee as its URI for a group and its canonical id for a user,
    which is how the document distinguishes the two.
    """
    out = []
    for grant in doc["Grants"]:
        who = grant["Grantee"].get("URI") or grant["Grantee"].get("ID")
        out.append((who, grant["Permission"]))
    return out


# ── bodies ───────────────────────────────────────────────────────────


def payload(n: int) -> bytes:
    """`n` bytes that are not all the same, so a truncation shows."""
    return bytes((i * 7 + 11) % 251 for i in range(n))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def random_file(size: int) -> tuple[str, str]:
    """`size` bytes of noise in a local temp file, and their md5.

    Noise rather than a pattern: the bucket's dataset compresses, and a
    pattern that shrinks a hundredfold proves nothing about a transfer.
    """
    import tempfile

    md5 = hashlib.md5()
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        left = size
        while left:
            block = os.urandom(min(left, 1 << 20))
            f.write(block)
            md5.update(block)
            left -= len(block)
        return f.name, md5.hexdigest()


def md5_of(path: str) -> str:
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            md5.update(block)
    return md5.hexdigest()


def drain(s3, bucket: str, prefix: str = "") -> None:
    """Delete every key under `prefix`, in as many passes as it takes.

    One pass is not enough on a filesystem: a directory row is listed
    before the keys beneath it and deleting a *populated* marker is a
    no-op, so a directory survives its own visit and is only removable
    once the pass that followed emptied it.
    """
    for _ in range(16):
        seen = 0
        token = None
        while True:
            kwargs = {"Bucket": bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            page = s3.list_objects_v2(**kwargs)
            for obj in page.get("Contents", []):
                seen += 1
                s3.delete_object(Bucket=bucket, Key=obj["Key"])
            token = page.get("NextContinuationToken")
            if not page.get("IsTruncated"):
                break
        if seen == 0:
            return
    raise AssertionError(f"{bucket}/{prefix} would not drain")


# ── requests botocore will not model ─────────────────────────────────


class RawResponse:
    """Just enough of a response for a raw assertion.

    `headers` is here because an SDK is not a transparent window onto
    them: botocore discards an error body's `RequestId` in favour of the
    header's, so a test comparing the two through `ResponseMetadata`
    compares the header with itself.
    """

    def __init__(self, status_code: int, text: str, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


def raw_request(s3, method: str, path: str, body: bytes | None = None, headers: dict[str, str] | None = None):
    """One signed request through the client's own session.

    Signed as `GetBucketLocation` because a SigV4 signature covers the
    method, the path and the headers rather than the operation name —
    and because `PutObject`'s own signing hooks would add a streaming
    checksum these cases have no use for.
    """
    import botocore.awsrequest

    req = botocore.awsrequest.AWSRequest(
        method=method,
        url=f"{s3.meta.endpoint_url}{path}",
        data=body,
        headers=headers or {},
    )
    s3._request_signer.sign("GetBucketLocation", req)
    return s3._endpoint.http_session.send(req.prepare())


def raw_query(s3, bucket: str, params: dict[str, str], key: str | None = None) -> RawResponse:
    """A signed GET with query parameters boto3 will not construct.

    Some cases are about values an SDK refuses to send — an empty token,
    a non-numeric `max-keys` — which are exactly the values a
    hand-rolled client sends. Others are about the bytes on the wire,
    which an SDK may decode before a test can see them.

    `key` names an object-level sub-resource (`?uploadId=`, `?tagging`);
    without it the target is the bucket.
    """
    import urllib.parse

    target = f"{bucket}/{urllib.parse.quote(key)}" if key else bucket
    query = urllib.parse.urlencode(params)
    resp = raw_request(s3, "GET", f"/{target}?{query}")
    return RawResponse(resp.status_code, resp.content.decode("utf-8", "replace"), dict(resp.headers))


def code_in(body: bytes | str) -> str | None:
    """The `<Code>` of an error document, or None."""
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
    if "<Code>" not in text:
        return None
    return text.split("<Code>", 1)[1].split("</Code>", 1)[0]
