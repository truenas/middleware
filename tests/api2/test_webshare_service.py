import pytest
from truenas_api_client import ClientException

from middlewared.test.integration.utils import call, non_ha_test

pytestmark = non_ha_test


@pytest.mark.parametrize("action", ["START", "RESTART"])
def test_control_requires_truenas_connect(action):
    with pytest.raises(ClientException) as e:
        call("service.control", action, "webshare", {"silent": False}, job=True)

    assert "TrueNAS Connect" in e.value.error
    svc = call("service.query", [["service", "=", "webshare"]], {"get": True})
    assert svc["state"] == "STOPPED"
