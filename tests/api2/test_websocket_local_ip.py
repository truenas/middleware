from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.client import truenas_server


def test_websocket_local_ip():
    """This tests to ensure we return the local IP address
    of the TrueNAS system based on the websocket session."""
    assert call("interface.websocket_local_ip") == truenas_server.ip
