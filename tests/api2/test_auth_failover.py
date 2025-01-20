import pytest

from middlewared.test.integration.utils import call, password, truenas_server
from truenas_api_client import Client

from auto_config import ha


@pytest.mark.skipif(not ha, reason="Test only valid for HA")
def test_auth_on_standby_node():
    ha_ips = truenas_server.ha_ips()

    with Client(f"ws://{ha_ips['standby']}/api/current") as c:
        assert c.call("auth.login_ex", {
            "mechanism": "PASSWORD_PLAIN",
            "username": "root",
            "password": password(),
        }) == {"response_type": "REDIRECT", "urls": call("failover.get_ips")}
