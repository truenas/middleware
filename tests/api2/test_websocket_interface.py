from auto_config import interface
from middlewared.test.integration.utils import call


def test_websocket_interface():
    """This tests to ensure we return the interface name
    by which the websocket connection has been established."""
    assert call("interface.websocket_interface")["id"] == interface
