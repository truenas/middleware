import asyncio
import socket
import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from middlewared.plugins.device_ import netlink_events
from middlewared.plugins.device_.netlink_events import (
    IFA_ADDRESS,
    IFA_CACHEINFO,
    IFA_LABEL,
    RTM_DELADDR,
    RTM_NEWADDR,
    is_address_refresh,
    parse_ifaddr_message,
    process_netlink_data,
)


def rtattr(attr_type: int, payload: bytes) -> bytes:
    header = struct.pack("HH", 4 + len(payload), attr_type)
    padding = b"\x00" * ((4 - len(payload) % 4) % 4)
    return header + payload + padding


def addr_msg(
    msg_type: int = RTM_NEWADDR,
    address: str = "2001:db8::1",
    prefixlen: int = 64,
    index: int = 2,
    label: str = "enp1s0",
    cacheinfo: tuple[int, int, int, int] | None = None,
) -> bytes:
    """Build a binary netlink address message as the kernel would send it.

    cacheinfo is (prefered, valid, cstamp, tstamp) or None to omit the
    IFA_CACHEINFO attribute entirely.
    """
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    attrs = rtattr(IFA_ADDRESS, socket.inet_pton(family, address))
    attrs += rtattr(IFA_LABEL, label.encode() + b"\x00")
    if cacheinfo is not None:
        attrs += rtattr(IFA_CACHEINFO, struct.pack("IIII", *cacheinfo))
    payload = struct.pack("BBBBI", family, prefixlen, 0, 0, index) + attrs
    header = struct.pack("IHHII", 16 + len(payload), msg_type, 0, 0, 0)
    return header + payload


def failing_sock() -> MagicMock:
    """A netlink socket stand in whose queries fail.

    get_interface_addresses swallows the error and returns an empty list,
    keeping the generator under test synchronous and hermetic.
    """
    sock = MagicMock()
    sock.recv.side_effect = OSError("no kernel in unit tests")
    return sock


def events_from(*messages: bytes) -> list[dict]:
    return list(process_netlink_data(failing_sock(), b"".join(messages)))


class TestAddressRefreshFilter:
    def test_new_address_yields_event(self):
        """Equal creation and update stamps mean a genuinely new address."""
        events = events_from(addr_msg(cacheinfo=(300, 300, 1000, 1000)))
        assert len(events) == 1
        assert events[0]["event"] == "add"
        assert events[0]["ip"] == "2001:db8::1/64"

    def test_lifetime_refresh_is_dropped(self):
        """An update stamp ahead of the creation stamp is an RA refresh."""
        assert events_from(addr_msg(cacheinfo=(300, 300, 1000, 2500))) == []

    def test_missing_cacheinfo_fails_open(self):
        assert len(events_from(addr_msg(cacheinfo=None))) == 1

    def test_short_cacheinfo_fails_open(self):
        truncated = rtattr(IFA_CACHEINFO, struct.pack("II", 300, 300))
        payload = struct.pack("BBBBI", socket.AF_INET6, 64, 0, 0, 2)
        payload += rtattr(IFA_ADDRESS, socket.inet_pton(socket.AF_INET6, "2001:db8::1"))
        payload += rtattr(IFA_LABEL, b"enp1s0\x00") + truncated
        msg = struct.pack("IHHII", 16 + len(payload), RTM_NEWADDR, 0, 0, 0) + payload
        assert len(events_from(msg)) == 1

    def test_deladdr_is_never_filtered(self):
        """Removal of a previously refreshed address is a real change."""
        events = events_from(addr_msg(msg_type=RTM_DELADDR, cacheinfo=(300, 300, 1000, 9000)))
        assert len(events) == 1
        assert events[0]["event"] == "remove"

    def test_ipv4_refresh_is_dropped(self):
        """A DHCP renewal of the same lease re-announces the same address."""
        assert events_from(addr_msg(address="10.0.0.5", prefixlen=24, cacheinfo=(600, 600, 50, 4000))) == []

    def test_mixed_batch_only_yields_real_changes(self):
        """One recv can carry several messages and only real changes surface."""
        events = events_from(
            addr_msg(cacheinfo=(300, 300, 1000, 2000)),
            addr_msg(address="10.0.0.5", prefixlen=24, cacheinfo=(600, 600, 3000, 3000)),
            addr_msg(cacheinfo=(300, 300, 1000, 2500)),
        )
        assert [e["ip"] for e in events] == ["10.0.0.5/24"]

    def test_predicate_direct(self):
        refreshed = parse_ifaddr_message(addr_msg(cacheinfo=(300, 300, 1, 2))[16:])
        brand_new = parse_ifaddr_message(addr_msg(cacheinfo=(300, 300, 7, 7))[16:])
        assert is_address_refresh(RTM_NEWADDR, refreshed) is True
        assert is_address_refresh(RTM_NEWADDR, brand_new) is False
        assert is_address_refresh(RTM_DELADDR, refreshed) is False


class TestVendorRestartCoalescing:
    @pytest.fixture
    def dbus_env(self, monkeypatch):
        monkeypatch.setattr(netlink_events, "IX_VEND_LOCK", asyncio.Lock())
        monkeypatch.setattr(netlink_events, "_restart_queued", False)
        dbus_mock = MagicMock()
        monkeypatch.setattr(netlink_events, "system_dbus", dbus_mock)
        middleware = MagicMock()
        middleware.call = AsyncMock(return_value=True)
        return middleware, dbus_mock

    @pytest.mark.asyncio
    async def test_requests_during_restart_collapse_into_one_waiter(self, dbus_env):
        """Requests made while a restart runs produce one queued restart, never a pileup."""
        middleware, dbus_mock = dbus_env
        first_started = asyncio.Event()
        release_first = asyncio.Event()

        async def dbus_action(unit, action):
            if dbus_mock.call_unit_action_and_wait.await_count == 1:
                first_started.set()
                await release_first.wait()

        dbus_mock.call_unit_action_and_wait = AsyncMock(side_effect=dbus_action)

        task1 = asyncio.ensure_future(netlink_events._systemctl_restart_ixvendor(middleware))
        await first_started.wait()

        # Five requests while the restart is blocked mid run
        extra = [asyncio.ensure_future(netlink_events._systemctl_restart_ixvendor(middleware)) for _ in range(5)]
        await asyncio.sleep(0)
        assert dbus_mock.call_unit_action_and_wait.await_count == 1

        release_first.set()
        await asyncio.gather(task1, *extra)
        # They collapsed into exactly one follow up restart
        assert dbus_mock.call_unit_action_and_wait.await_count == 2
        assert netlink_events._restart_queued is False
        assert not netlink_events.IX_VEND_LOCK.locked()

    @pytest.mark.asyncio
    async def test_sequential_requests_each_restart(self, dbus_env):
        middleware, dbus_mock = dbus_env
        dbus_mock.call_unit_action_and_wait = AsyncMock()
        await netlink_events._systemctl_restart_ixvendor(middleware)
        await netlink_events._systemctl_restart_ixvendor(middleware)
        assert dbus_mock.call_unit_action_and_wait.await_count == 2

    @pytest.mark.asyncio
    async def test_failed_restart_leaves_clean_state(self, dbus_env):
        """A restart failure releases the lock and clears the queued flag."""
        middleware, dbus_mock = dbus_env
        dbus_mock.call_unit_action_and_wait = AsyncMock(side_effect=[RuntimeError("dbus down"), None])
        with pytest.raises(RuntimeError):
            await netlink_events._systemctl_restart_ixvendor(middleware)
        assert netlink_events._restart_queued is False
        assert not netlink_events.IX_VEND_LOCK.locked()
        await netlink_events._systemctl_restart_ixvendor(middleware)
        assert dbus_mock.call_unit_action_and_wait.await_count == 2
