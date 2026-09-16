"""Presigned URLs: a signature carried in the query rather than a header.

The URL *is* the authentication, so it has to travel over a plain HTTP
client — a boto3 client would sign it again and prove nothing. This is
the only place a presign meets a real signer end to end.

What each case pins is a different part of the canonical request: the
method, the resource and the window are all inside the signature by
construction, so a link that authorized one GET of one key for one hour
must not authorize anything else.
"""

import http.client
import ssl
import time
import urllib.parse

import pytest

PREFIX = "presign/"


def raw(url, method="GET", body=None):
    """One unsigned request at a presigned URL.

    Plain `http.client` rather than requests or boto3: nothing here may
    add a header, because a header the signature did not cover would
    change the answer for a reason the case is not about.
    """
    parts = urllib.parse.urlparse(url)
    if parts.scheme == "https":
        conn = http.client.HTTPSConnection(parts.netloc, timeout=10, context=ssl._create_unverified_context())
    else:
        conn = http.client.HTTPConnection(parts.netloc, timeout=10)
    try:
        target = parts.path + (f"?{parts.query}" if parts.query else "")
        conn.request(method, target, body=body, headers={})
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


@pytest.fixture(scope="module")
def signed(s3, bucket):
    """One object, and a link that reads it for an hour."""
    key = f"{PREFIX}object.txt"
    body = b"presigned payload"
    s3.put_object(Bucket=bucket, Key=key, Body=body)
    url = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600)
    yield key, body, url
    s3.delete_object(Bucket=bucket, Key=key)


def test_a_presigned_get_inside_its_window_serves(s3, bucket, signed):
    _key, body, url = signed
    status, data = raw(url)
    assert status == 200, data[:200]
    assert data == body


def test_a_presigned_get_cannot_put(s3, bucket, signed):
    """The method is signed, so this is a different request than the one
    that was authorized."""
    _key, _body, url = signed
    status, _ = raw(url, method="PUT", body=b"overwrite")
    assert status == 403


def test_a_presigned_get_cannot_move_keys(s3, bucket, signed):
    """The resource is signed too — a link is for one object, and
    rewriting the path in it authorizes nothing."""
    key, _body, url = signed
    other = url.replace(urllib.parse.quote(key), urllib.parse.quote(f"{PREFIX}other.txt"))
    assert other != url, "the substitution has to actually change the URL"
    status, _ = raw(other)
    assert status == 403


def test_an_expired_link_is_refused(s3, bucket, signed):
    """One second is enough: the window has closed by the time the
    request lands, and the signature is still perfectly valid — which is
    the case a shared URL actually reaches."""
    key, _body, _url = signed
    expiring = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=1)
    time.sleep(2)
    status, _ = raw(expiring)
    assert status == 403


def test_a_presigned_put_stores(s3, bucket):
    """A write the client never signed as a header, which is the other
    half of what presigning is for."""
    key = f"{PREFIX}written.txt"
    url = s3.generate_presigned_url("put_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600)
    try:
        status, data = raw(url, method="PUT", body=b"written through a presign")
        assert status == 200, data[:200]
        assert s3.get_object(Bucket=bucket, Key=key)["Body"].read() == b"written through a presign"
    finally:
        s3.delete_object(Bucket=bucket, Key=key)
