import random
import string

import pytest

from truenas_api_client import Client

from middlewared.test.integration.assets.account import unprivileged_user
from middlewared.test.integration.assets.cloud_sync import credential
from middlewared.test.integration.utils import call, password, websocket_url


@pytest.fixture(scope="module")
def c():
    call("rate.limit.cache_clear")
    with Client(websocket_url() + "/websocket") as c:
        c.call("auth.login_ex", {
            "mechanism": "PASSWORD_PLAIN",
            "username": "root",
            "password": password(),
        })
        yield c


@pytest.fixture(scope="module")
def unprivileged_client():
    call("rate.limit.cache_clear")
    suffix = "".join([random.choice(string.ascii_lowercase + string.digits) for _ in range(8)])
    with unprivileged_user(
        username=f"unprivileged_{suffix}",
        group_name=f"unprivileged_users_{suffix}",
        privilege_name=f"Unprivileged users ({suffix})",
        allowlist=[],
        roles=["READONLY_ADMIN"],
        web_shell=False,
    ) as t:
        with Client(websocket_url() + "/websocket") as c:
            c.call("auth.login_ex", {
                "mechanism": "PASSWORD_PLAIN",
                "username": t.username,
                "password": t.password,
            })
            yield c


@pytest.fixture(scope="function")
def clear_ratelimit():
    call("rate.limit.cache_clear")


@pytest.fixture(scope="module")
def ftp_credential():
    with credential({
        "provider": {
            "type": "FTP",
            "host": "localhost",
            "port": 21,
            "user": "test",
            "pass": "",
        },
    }) as cred:
        yield cred


def test_adapts_cloud_credentials(c, ftp_credential):
    result = c.call("cloudsync.credentials.get_instance", ftp_credential["id"])
    assert result["provider"] == "FTP"


def test_adapts_cloud_credentials_for_unprivileged(unprivileged_client, ftp_credential):
    result = unprivileged_client.call("cloudsync.credentials.get_instance", ftp_credential["id"])
    assert result["attributes"] == "********"
