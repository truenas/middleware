from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ("SyncData",)


@dataclass(slots=True, frozen=True, kw_only=True)
class SyncData:
    """All database data needed for interface sync, queried once."""

    interfaces: dict[str, dict] = field(default_factory=dict)
    """Interface configs: {name: {"interface": {...}, "aliases": [...]}}"""

    bonds: list[dict] = field(default_factory=list)
    """network.lagginterface records"""

    bond_members: list[dict] = field(default_factory=list)
    """network.lagginterfacemembers records"""

    vlans: list[dict] = field(default_factory=list)
    """network.vlan records"""

    bridges: list[dict] = field(default_factory=list)
    """network.bridge records"""

    node: str = ""
    """Failover node ("A", "B", or "")"""

    def is_bond_member(self, name: str) -> bool:
        """Check if interface is a bond member (should skip MTU)."""
        return any(m["lagg_physnic"] == name for m in self.bond_members)

    def get_bond_members_for(self, bond_id: int) -> list[dict]:
        """Get member records for a specific bond."""
        return [m for m in self.bond_members if m["lagg_interfacegroup_id"] == bond_id]

    @property
    def parent_interfaces(self) -> set[str]:
        """Interfaces that are parents/members of virtual interfaces."""
        parents = set()
        for member in self.bond_members:
            parents.add(member["lagg_physnic"])
        for vlan in self.vlans:
            parents.add(vlan["vlan_pint"])
        for bridge in self.bridges:
            parents.update(bridge["members"])
        return parents
