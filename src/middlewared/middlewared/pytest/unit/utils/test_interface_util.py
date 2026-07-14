import unittest.mock

from middlewared.utils import interface
from middlewared.utils.interface import (
    IFACE_LINK_STATE_MAX_WAIT,
    wait_for_default_interface_link_state_up,
)


def test_default_interface_already_present():
    # Route is there on the first read, link comes up: no polling needed.
    with (
        unittest.mock.patch.object(interface, "get_default_interface", return_value="br1") as gdi,
        unittest.mock.patch.object(interface, "wait_on_interface_link_state_up", return_value=True),
        unittest.mock.patch.object(interface.time, "sleep") as sleep,
    ):
        assert wait_for_default_interface_link_state_up() == ("br1", True)
        gdi.assert_called_once()
        sleep.assert_not_called()


def test_default_interface_appears_late():
    # The boot race: no default route for the first couple of reads (DHCP/bridge still
    # converging), then it shows up. We must keep polling rather than give up immediately.
    with (
        unittest.mock.patch.object(interface, "get_default_interface", side_effect=[None, None, "br1"]) as gdi,
        unittest.mock.patch.object(interface, "wait_on_interface_link_state_up", return_value=True),
        unittest.mock.patch.object(interface.time, "sleep") as sleep,
    ):
        assert wait_for_default_interface_link_state_up() == ("br1", True)
        assert gdi.call_count == 3
        assert sleep.call_count == 2


def test_no_default_interface_within_window():
    # Genuinely network-less box: never find a route, return (None, False) after the full window.
    with (
        unittest.mock.patch.object(interface, "get_default_interface", return_value=None) as gdi,
        unittest.mock.patch.object(interface, "wait_on_interface_link_state_up") as wlsu,
        unittest.mock.patch.object(interface.time, "sleep") as sleep,
    ):
        assert wait_for_default_interface_link_state_up() == (None, False)
        assert gdi.call_count == IFACE_LINK_STATE_MAX_WAIT
        assert sleep.call_count == IFACE_LINK_STATE_MAX_WAIT
        wlsu.assert_not_called()


def test_default_interface_present_but_link_never_up():
    # Route exists but the interface never reaches operstate=up.
    with (
        unittest.mock.patch.object(interface, "get_default_interface", return_value="br1"),
        unittest.mock.patch.object(interface, "wait_on_interface_link_state_up", return_value=False),
        unittest.mock.patch.object(interface.time, "sleep") as sleep,
    ):
        assert wait_for_default_interface_link_state_up() == ("br1", False)
        sleep.assert_not_called()
