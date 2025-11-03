import io
import json

import pytest

from middlewared.test.integration.utils import call, session, ssh, url


@pytest.fixture(scope="module")
def otp_enabled():
    call("auth.twofactor.update", {"enabled": True})

    try:
        yield
    finally:
        ssh("midclt call auth.twofactor.update '{\"enabled\": false}'")


def test_otp_http_basic_auth_upload(otp_enabled):
    with session() as s:
        r = s.post(
            f"{url()}/_upload/",
            data={
                "data": json.dumps({
                    "method": "filesystem.put",
                    "params": ["/tmp/upload"],
                })
            },
            files={
                "file": io.BytesIO(b"test"),
            },
        )
        assert r.status_code == 401
        assert r.text == "HTTP Basic Auth is unavailable when OTP is enabled"
