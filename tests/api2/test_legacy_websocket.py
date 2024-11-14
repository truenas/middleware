import logging

import pytest

from truenas_api_client import Client

from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.assets.cloud_sync import credential
from middlewared.test.integration.utils import call, mock, password, websocket_url

logger = logging.getLogger(__name__)


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


def test_does_not_perform_output_validation_for_full_admin(c):
    with api_key():
        key = call("api_key.query")[0]
        with mock("api_key.item_extend", return_value={**key, "invalid_field": 1}):
            c.call("api_key.get_instance", key["id"])
