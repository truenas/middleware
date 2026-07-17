import pytest

from middlewared.test.integration.assets.crypto import imported_certificate
from middlewared.test.integration.assets.kmip import KMIP_HOST, KMIP_PORT, kmip_enabled, kmip_server
from middlewared.test.integration.utils import call
from truenas_api_client.exc import ValidationErrors


@pytest.fixture(scope="module")
def kmip_certificate():
    """Run the fake KMIP server and import its certificate into the middleware store."""
    with kmip_server() as srv:
        with imported_certificate("kmip_test_cert", srv["cert"], srv["key"]) as cert:
            yield cert


def test_kmip_config_defaults():
    config = call("kmip.config")
    assert config["enabled"] is False
    assert config["port"] == 5696
    assert config["ssl_version"] == "PROTOCOL_TLSv1_2"
    assert config["manage_zfs_keys"] is False
    assert config["manage_sed_disks"] is False


def test_kmip_enable_connects_to_server(kmip_certificate):
    with kmip_enabled(kmip_certificate["id"]):
        config = call("kmip.config")
        assert config["enabled"] is True
        assert config["server"] == KMIP_HOST
        assert config["port"] == KMIP_PORT
        assert config["certificate"] == kmip_certificate["id"]
        assert config["certificate_authority"] == kmip_certificate["id"]
        # No datasets/disks are managed, so nothing should be pending sync.
        assert call("kmip.kmip_sync_pending") is False

    # After the context manager exits KMIP should be disabled again.
    assert call("kmip.config")["enabled"] is False


def test_kmip_enable_unreachable_server_fails(kmip_certificate):
    # Nothing is listening on this port, so the pre-save connection test must fail.
    with pytest.raises(ValidationErrors) as ve:
        with kmip_enabled(kmip_certificate["id"], port=5699):
            pass

    assert any("kmip_update.server" == error.attribute for error in ve.value.errors), ve.value.errors
    assert call("kmip.config")["enabled"] is False
