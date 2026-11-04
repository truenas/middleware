import pytest
from truenas_api_client import ClientException

from middlewared.test.integration.utils import call


@pytest.fixture(scope="module", autouse=True)
def community_edition():
    if call("system.product_type") != "COMMUNITY_EDITION" or call("failover.licensed"):
        pytest.skip("Webshare is only gated on TrueNAS Connect on non-HA Community Edition systems")


@pytest.mark.parametrize("action", ["START", "RESTART"])
def test_control_requires_truenas_connect(action):
    with pytest.raises(ClientException) as e:
        call("service.control", action, "webshare", {"silent": False}, job=True)

    assert "TrueNAS Connect" in e.value.error
    svc = call("service.query", [["service", "=", "webshare"]], {"get": True})
    assert svc["state"] == "STOPPED"
