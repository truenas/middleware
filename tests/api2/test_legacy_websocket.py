import pytest

from truenas_api_client import Client

from middlewared.test.integration.assets.cloud_sync import credential
from middlewared.test.integration.utils import password, websocket_url


@pytest.fixture(scope="module")
def c():
    with Client(websocket_url() + "/websocket") as c:
        c.call("auth.login_ex", {
            "mechanism": "PASSWORD_PLAIN",
            "username": "root",
            "password": password(),
        })
        yield c


def test_adapts_cloud_credentials(c):
    with credential({
        "provider": {
            "type": "FTP",
            "host": "localhost",
            "port": 21,
            "user": "test",
            "pass": "",
        },
    }) as cred:
        result = c.call("cloudsync.credentials.get_instance", cred["id"])
        assert result["provider"] == "FTP"
