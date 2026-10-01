import pytest
from truenas_api_client import ClientException

from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.utils import call


@pytest.mark.parametrize("verb", ["START", "RESTART"])
def test_webshare_refuses_to_run_without_truenas_connect(verb):
    with entitled("WEBSHARE"):
        with pytest.raises(ClientException, match="TrueNAS Connect"):
            call("service.control", verb, "webshare", job=True)

    assert call("service.query", [["service", "=", "webshare"]], {"get": True})["state"] == "STOPPED"
