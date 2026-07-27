import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from middlewared.plugins.device_ import netlink_events


def make_event(
    index: int = 2,
    ips: tuple[str, ...] = ("10.0.0.5", "fe80::be24:11ff:fea2:a630"),
    iface: str = "enp1s0",
    event: str = "add",
    family: str = "inet6",
    ip: str | None = None,
) -> dict[str, Any]:
    """Build an ipaddress.change event payload as emitted by process_netlink_data.

    `ip` is the address the netlink message was about (for a remove event it is
    no longer part of `available_ips`); defaults to the first available address.
    """
    return {
        "fields": {
            "iface": iface,
            "ip": ip if ip is not None else f"{ips[0]}/64",
            "event": event,
            "family": family,
            "scope": 0,
            "index": index,
            "broadcast": None,
            "available_ips": list(ips),
        }
    }


@pytest.fixture
def restart_env(monkeypatch):
    """Reset module state, zero the debounce delay, and stub the restart implementation."""
    monkeypatch.setattr(netlink_events, "_iface_ip_snapshot", {})
    monkeypatch.setattr(netlink_events, "_pending_vendor_restart", None)
    monkeypatch.setattr(netlink_events, "IX_VEND_DEBOUNCE_SECONDS", 0)
    restart_mock = AsyncMock()
    monkeypatch.setattr(netlink_events, "_systemctl_restart_ixvendor", restart_mock)
    middleware = MagicMock()
    middleware.create_task = lambda coro: asyncio.ensure_future(coro)
    return middleware, restart_mock


async def settle():
    """Let zero-delay call_later timers fire and their tasks run."""
    for _ in range(3):
        await asyncio.sleep(0)


class TestVendorRestartDedupe:
    @pytest.mark.asyncio
    async def test_lifetime_refresh_is_deduped(self, restart_env):
        """RTM_NEWADDR re-emitted for an RA lifetime refresh (unchanged address set) must not restart."""
        middleware, restart_mock = restart_env
        await netlink_events._restart_vendor_service(middleware, "CHANGED", make_event())
        for _ in range(5):
            await netlink_events._restart_vendor_service(middleware, "CHANGED", make_event())
        await settle()
        assert restart_mock.await_count == 1

    @pytest.mark.asyncio
    async def test_changed_address_set_restarts(self, restart_env):
        middleware, restart_mock = restart_env
        await netlink_events._restart_vendor_service(middleware, "CHANGED", make_event(ips=("10.0.0.5",)))
        await settle()
        await netlink_events._restart_vendor_service(middleware, "CHANGED", make_event(ips=("10.0.0.5", "2001:db8::1")))
        await settle()
        assert restart_mock.await_count == 2

    @pytest.mark.asyncio
    async def test_interfaces_tracked_independently(self, restart_env):
        middleware, restart_mock = restart_env
        await netlink_events._restart_vendor_service(middleware, "CHANGED", make_event(index=2, ips=("10.0.0.5",)))
        await settle()
        await netlink_events._restart_vendor_service(middleware, "CHANGED", make_event(index=3, ips=("172.16.0.1",)))
        await settle()
        assert restart_mock.await_count == 2
        # Repeats on either interface are deduped
        await netlink_events._restart_vendor_service(middleware, "CHANGED", make_event(index=2, ips=("10.0.0.5",)))
        await netlink_events._restart_vendor_service(middleware, "CHANGED", make_event(index=3, ips=("172.16.0.1",)))
        await settle()
        assert restart_mock.await_count == 2

    @pytest.mark.asyncio
    async def test_burst_is_coalesced_into_one_restart(self, restart_env):
        """Several distinct changes inside the debounce window yield a single restart."""
        middleware, restart_mock = restart_env
        for ips in (("10.0.0.5",), ("10.0.0.5", "2001:db8::1"), ("2001:db8::1",)):
            await netlink_events._restart_vendor_service(middleware, "CHANGED", make_event(ips=ips))
        await settle()
        assert restart_mock.await_count == 1

    @pytest.mark.asyncio
    async def test_empty_address_set_change_restarts(self, restart_env):
        """Losing the last address on an interface is a real change."""
        middleware, restart_mock = restart_env
        await netlink_events._restart_vendor_service(middleware, "CHANGED", make_event(ips=("10.0.0.5",)))
        await settle()
        await netlink_events._restart_vendor_service(
            middleware, "CHANGED", make_event(ips=(), event="remove", ip="10.0.0.5/24")
        )
        await settle()
        assert restart_mock.await_count == 2


class TestVendorRestartSerialization:
    @pytest.mark.asyncio
    async def test_restart_during_restart_waits_instead_of_dropping(self, monkeypatch):
        """A restart scheduled while another is running must still execute afterwards."""
        monkeypatch.setattr(netlink_events, "IX_VEND_LOCK", asyncio.Lock())
        first_started = asyncio.Event()
        release_first = asyncio.Event()

        async def dbus_action(unit, action):
            if dbus_mock.call_unit_action_and_wait.await_count == 1:
                first_started.set()
                await release_first.wait()

        dbus_mock = MagicMock()
        dbus_mock.call_unit_action_and_wait = AsyncMock(side_effect=dbus_action)
        monkeypatch.setattr(netlink_events, "system_dbus", dbus_mock)

        middleware = MagicMock()
        middleware.call2 = AsyncMock(return_value=True)

        task1 = asyncio.ensure_future(netlink_events._systemctl_restart_ixvendor(middleware))
        await first_started.wait()
        task2 = asyncio.ensure_future(netlink_events._systemctl_restart_ixvendor(middleware))
        await asyncio.sleep(0)
        assert dbus_mock.call_unit_action_and_wait.await_count == 1

        release_first.set()
        await asyncio.gather(task1, task2)
        assert dbus_mock.call_unit_action_and_wait.await_count == 2
