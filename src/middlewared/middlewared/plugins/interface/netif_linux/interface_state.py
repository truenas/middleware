from dataclasses import dataclass

from middlewared.plugins.interface.netif_linux.address.constants import AddressFamily, IFOperState
from middlewared.plugins.interface.netif_linux.address.netlink import (
    AddressInfo,
    DumpInterrupted,
    LinkInfo,
    get_address_netlink,
)
from middlewared.plugins.interface.netif_linux.bits import InterfaceFlags
from middlewared.plugins.interface.netif_linux.ethernet_settings import EthernetHardwareSettings
from middlewared.plugins.interface.netif_linux.utils import INTERNAL_INTERFACES

__all__ = (
    "InterfaceState",
    "list_interface_states",
)

# Prefixes that indicate a cloned/virtual interface
CLONED_PREFIXES = ("br", "vlan", "bond")

# Map operstate int to link state string
_OPERSTATE_TO_LINK_STATE = {
    IFOperState.UNKNOWN: "LINK_STATE_UNKNOWN",
    IFOperState.NOTPRESENT: "LINK_STATE_NOTPRESENT",
    IFOperState.DOWN: "LINK_STATE_DOWN",
    IFOperState.LOWERLAYERDOWN: "LINK_STATE_LOWERLAYERDOWN",
    IFOperState.TESTING: "LINK_STATE_TESTING",
    IFOperState.DORMANT: "LINK_STATE_DORMANT",
    IFOperState.UP: "LINK_STATE_UP",
}


def _flags_to_names(flags: int) -> list[str]:
    """Convert interface flags bitmask to list of flag names."""
    return [f.name for f in InterfaceFlags if flags & f]


def _address_to_alias_dict(addr: AddressInfo) -> dict:
    """Convert AddressInfo to the alias dict format expected by middleware."""
    if addr.family == AddressFamily.INET:
        af_name = "INET"
    elif addr.family == AddressFamily.INET6:
        af_name = "INET6"
    else:
        af_name = "LINK"

    result = {
        "type": af_name,
        "address": addr.address,
        "netmask": addr.prefixlen,
    }
    if addr.broadcast:
        result["broadcast"] = addr.broadcast
    return result


@dataclass(slots=True)
class InterfaceState:
    """
    Interface state information from netlink.

    Provides the same interface as the old Interface class for use in
    middleware's query() method.
    """

    name: str
    link: LinkInfo
    addresses: list[AddressInfo]

    @property
    def cloned(self) -> bool:
        """Whether this is a cloned/virtual interface."""
        return self.name.startswith(CLONED_PREFIXES) or self.name.startswith(
            INTERNAL_INTERFACES
        )

    @property
    def bus(self) -> str | None:
        """Parent bus type (e.g., 'usb', 'pci')."""
        return self.link.parentbus

    @property
    def link_state(self) -> str:
        """Link state as string (e.g., 'LINK_STATE_UP')."""
        return _OPERSTATE_TO_LINK_STATE.get(
            self.link.operstate, f"LINK_STATE_{self.link.operstate}"
        )

    def asdict(
        self, address_stats: bool = False, vrrp_config: list | None = None
    ) -> dict:
        """
        Build interface state dict compatible with Interface.asdict().

        This format is expected by middleware's iface_extend() method.
        """
        link = self.link
        link_state = _OPERSTATE_TO_LINK_STATE.get(
            link.operstate, f"LINK_STATE_{link.operstate}"
        )

        # Build aliases from addresses (only INET and INET6)
        aliases = [
            _address_to_alias_dict(addr)
            for addr in self.addresses
            if addr.family in (AddressFamily.INET, AddressFamily.INET6)
        ]

        state = {
            "name": self.name,
            "orig_name": self.name,
            "description": self.name,
            "mtu": link.mtu,
            "cloned": self.cloned,
            "flags": _flags_to_names(link.flags),
            "nd6_flags": [],  # Not parsed yet - rarely used
            "capabilities": [],
            "link_state": link_state,
            "media_type": "",
            "media_subtype": "",
            "active_media_type": "",
            "active_media_subtype": "",
            "supported_media": [],
            "media_options": None,
            "link_address": link.address or "",
            "permanent_link_address": link.perm_address,
            "hardware_link_address": link.perm_address or link.address or "",
            "aliases": aliases,
            "vrrp_config": vrrp_config,
            "rx_queues": link.num_rx_queues,
            "tx_queues": link.num_tx_queues,
        }

        # Add ethtool info (capabilities, media)
        with EthernetHardwareSettings(self.name) as dev:
            state.update(
                {
                    "capabilities": dev.enabled_capabilities,
                    "supported_media": dev.supported_media,
                    "media_type": dev.media_type,
                    "media_subtype": dev.media_subtype,
                    "active_media_type": dev.active_media_type,
                    "active_media_subtype": dev.active_media_subtype,
                }
            )

        # Bond-specific fields
        if self.name.startswith("bond"):
            state.update(self._get_bond_info())

        # VLAN-specific fields
        if self.name.startswith("vlan"):
            state.update(self._get_vlan_info())

        return state

    def _get_bond_info(self) -> dict:
        """Get bond/lagg specific info from sysfs."""
        result = {
            "protocol": None,
            "ports": [],
            "xmit_hash_policy": None,
            "lacpdu_rate": None,
        }

        try:
            # Read bond mode from sysfs
            with open(f"/sys/class/net/{self.name}/bonding/mode") as f:
                mode_str = f.read().strip().split()[0]
                # Map kernel mode names to our enum
                mode_map = {
                    "balance-rr": "ROUNDROBIN",
                    "active-backup": "FAILOVER",
                    "balance-xor": "LOADBALANCE",
                    "broadcast": "BROADCAST",
                    "802.3ad": "LACP",
                    "balance-tlb": "LOADBALANCE",
                    "balance-alb": "LOADBALANCE",
                }
                result["protocol"] = mode_map.get(mode_str, mode_str.upper())

            # Read ports/slaves
            with open(f"/sys/class/net/{self.name}/bonding/slaves") as f:
                slaves = f.read().strip().split()
                result["ports"] = [{"name": p, "flags": []} for p in slaves]

            # Read xmit_hash_policy
            with open(f"/sys/class/net/{self.name}/bonding/xmit_hash_policy") as f:
                policy = f.read().strip().split()[0]
                result["xmit_hash_policy"] = policy

            # Read lacpdu_rate (only for LACP mode)
            if result["protocol"] == "LACP":
                with open(f"/sys/class/net/{self.name}/bonding/lacp_rate") as f:
                    rate = f.read().strip().split()[0]
                    result["lacpdu_rate"] = rate

        except (OSError, IndexError):
            pass

        return result

    def _get_vlan_info(self) -> dict:
        """Get VLAN specific info."""
        result = {
            "parent": None,
            "tag": None,
            "pcp": None,
        }

        try:
            # Read VLAN info from /proc/net/vlan/<name>
            with open(f"/proc/net/vlan/{self.name}") as f:
                for line in f:
                    if "VID:" in line:
                        parts = line.split()
                        vid_idx = parts.index("VID:")
                        result["tag"] = int(parts[vid_idx + 1])
                    elif "Device:" in line:
                        parts = line.split()
                        dev_idx = parts.index("Device:")
                        result["parent"] = parts[dev_idx + 1]
        except (OSError, ValueError, IndexError):
            pass

        return result


def list_interface_states(max_retries: int = 3) -> dict[str, InterfaceState]:
    """
    Get all network interfaces using pure netlink.

    Returns a dict mapping interface name to InterfaceState.
    This is a drop-in replacement for netif.list_interfaces().
    """
    for attempt in range(1, max_retries + 1):
        try:
            nl = get_address_netlink()

            # Get all links
            links = nl.get_links()

            # Get all addresses with interface names
            all_addresses = nl.get_addresses()

            # Group addresses by interface name
            addresses_by_name: dict[str, list[AddressInfo]] = {}
            for addr in all_addresses:
                if addr.ifname:
                    if addr.ifname not in addresses_by_name:
                        addresses_by_name[addr.ifname] = []
                    addresses_by_name[addr.ifname].append(addr)

            # Build InterfaceState objects
            result: dict[str, InterfaceState] = {}
            for name, link in links.items():
                result[name] = InterfaceState(
                    name=name,
                    link=link,
                    addresses=addresses_by_name.get(name, []),
                )

            return result

        except DumpInterrupted:
            if attempt < max_retries:
                continue
            raise
