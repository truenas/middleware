from __future__ import annotations

import contextlib
import dataclasses
import os
import socket
import struct

from middlewared.plugins.service_.services.base import (
    call_unit_action,
    call_unit_action_and_wait,
)

__all__ = ("DHCPLease", "DHCPStatus", "dhcp_leases", "dhcp_start", "dhcp_status", "dhcp_stop")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class DHCPStatus:
    running: bool
    pid: int | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class DHCPLease:
    ip_address: str | None = None
    subnet_mask: str | None = None
    subnet_cidr: str | None = None
    broadcast_address: str | None = None
    routers: str | None = None
    domain_name_servers: str | None = None
    domain_name: str | None = None
    dhcp_lease_time: str | None = None
    dhcp_server_identifier: str | None = None
    pid: int | None = None


_SIZEOF_SIZE_T = 8
_SOCK_TIMEOUT = 5.0


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed prematurely")
        buf += chunk
    return buf


def _parse_env_block(data: bytes) -> dict[str, str]:
    """Parse a NULL-separated block of KEY=VALUE env strings from dhcpcd."""
    result = {}
    for item in data.split(b"\0"):
        if not item:
            continue
        decoded = item.decode("utf-8", errors="replace")
        if "=" in decoded:
            key, _, value = decoded.partition("=")
            result[key] = value
    return result


@contextlib.contextmanager
def _connect_dhcpcd(interface: str):
    """Connect to the dhcpcd control socket for an interface."""
    sock_path = f"/run/dhcpcd/{interface}.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(_SOCK_TIMEOUT)
        s.connect(sock_path)
        yield s


def _env_to_lease(env: dict[str, str]) -> DHCPLease:
    """Convert a raw dhcpcd env dict to a DHCPLease dataclass."""
    pid = None
    with contextlib.suppress(KeyError, ValueError):
        pid = int(env["pid"])

    return DHCPLease(
        ip_address=env.get("new_ip_address"),
        subnet_mask=env.get("new_subnet_mask"),
        subnet_cidr=env.get("new_subnet_cidr"),
        broadcast_address=env.get("new_broadcast_address"),
        routers=env.get("new_routers"),
        domain_name_servers=env.get("new_domain_name_servers"),
        domain_name=env.get("new_domain_name"),
        dhcp_lease_time=env.get("new_dhcp_lease_time"),
        dhcp_server_identifier=env.get("new_dhcp_server_identifier"),
        pid=pid,
    )


async def dhcp_start(interface: str, wait: int | None = None) -> None:
    """Start the ix-dhcpcd systemd service for an interface via D-Bus.

    Args:
        interface: Network interface name (e.g. "ens1").
        wait: If None, fire-and-forget. If an int, wait up to that many
              seconds (clamped to [5, 120]) for the service to start.
    """
    unit_name = f"ix-dhcpcd@{interface}.service"
    if wait is None:
        await call_unit_action(unit_name, "Start")
    else:
        await call_unit_action_and_wait(
            unit_name, "Start", timeout=min(120, max(5, wait))
        )


def dhcp_status(interface: str) -> DHCPStatus:
    """Check if dhcpcd is running for an interface by probing its control socket.

    Attempts to connect to /run/dhcpcd/{interface}.sock. If the socket
    accepts the connection, dhcpcd is running. The PID is extracted from
    lease data and validated with a signal check.
    """
    lease = dhcp_leases(interface)
    if lease is None:
        return DHCPStatus(running=False)

    pid = None
    if lease.pid is not None:
        with contextlib.suppress(OSError):
            os.kill(lease.pid, 0)
            pid = lease.pid

    return DHCPStatus(running=True, pid=pid)


async def dhcp_stop(interface: str) -> None:
    """Stop the ix-dhcpcd systemd service for an interface via D-Bus.

    Waits for the service to fully stop and all processes to exit.
    """
    unit_name = f"ix-dhcpcd@{interface}.service"
    await call_unit_action_and_wait(unit_name, "Stop")


def dhcp_leases(interface: str) -> DHCPLease | None:
    """Query dhcpcd lease information via the control socket.

    Sends the --getinterfaces command to /run/dhcpcd/{interface}.sock and
    parses the response. Returns a DHCPLease for the active DHCP lease
    (the entry with protocol=dhcp), or None if dhcpcd is not running or
    no lease has been obtained.
    """
    try:
        with _connect_dhcpcd(interface) as s:
            s.sendall(b"--getinterfaces\0")
            nifaces = struct.unpack("@Q", _recv_exact(s, _SIZEOF_SIZE_T))[0]
            for _ in range(nifaces):
                data_len = struct.unpack("@Q", _recv_exact(s, _SIZEOF_SIZE_T))[0]
                data = _recv_exact(s, data_len)
                env = _parse_env_block(data)
                if env.get("protocol") == "dhcp":
                    return _env_to_lease(env)
        return None
    except OSError:
        return None
