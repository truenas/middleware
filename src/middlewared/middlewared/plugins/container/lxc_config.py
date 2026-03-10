from __future__ import annotations

import ipaddress

import middlewared.sqlalchemy as sa
from middlewared.api.current import LXCConfigEntry, LXCConfigUpdate
from middlewared.service import ConfigServicePart, ValidationErrors
from middlewared.utils.network import system_ips_to_cidrs, validate_network_overlaps

from .bridge import BRIDGE_AUTO, bridge_choices
from .info import pool_choices


# Network defaults for the auto-managed container bridge (truenasbr0).
# Chosen to avoid overlap with:
#   - Docker address pools: 172.17.0.0/12 (v4), fdd0::/48 (v6)
#   - Incus auto-generated ranges: 10.x.x.0/24 (v4), fd42:random::/64 (v6)
DEFAULT_V4_NETWORK = '172.200.0.0/24'
DEFAULT_V6_NETWORK = 'fd42:4c58:43ae::/64'


class ContainerConfigModel(sa.Model):
    __tablename__ = "container_config"

    id = sa.Column(sa.Integer(), primary_key=True)
    bridge = sa.Column(sa.Text(), nullable=True)
    preferred_pool = sa.Column(sa.Text(), nullable=True)
    v4_network = sa.Column(sa.String(), nullable=False, default=DEFAULT_V4_NETWORK)
    v6_network = sa.Column(sa.String(), nullable=False, default=DEFAULT_V6_NETWORK)


class LXCConfigServicePart(ConfigServicePart[LXCConfigEntry]):
    _datastore = 'container.config'
    _entry = LXCConfigEntry

    async def do_update(self, data: LXCConfigUpdate) -> LXCConfigEntry:
        old_config = await self.config()
        config = old_config.updated(data)

        if config.bridge in ("", BRIDGE_AUTO):
            config = config.model_copy(update={"bridge": None})

        verrors = ValidationErrors()

        if (config.bridge or BRIDGE_AUTO) not in await bridge_choices(self):
            verrors.add("lxc_config_update.bridge", "Invalid bridge")

        if config.bridge is None and config.v4_network is None and config.v6_network is None:
            verrors.add(
                "lxc_config_update.bridge",
                "You must specify either IPv4 network of IPv6 network for automatically-configured bridge"
            )

        if config.preferred_pool and config.preferred_pool not in await pool_choices(self):
            verrors.add("lxc_config_update.preferred_pool", "Pool not found.")

        for k in ("v4_network", "v6_network"):
            v = getattr(config, k)
            if v is not None:
                if ipaddress.ip_interface(v).network.num_addresses < 4:
                    verrors.add(f"lxc_config_update.{k}", "The network must have at least 4 addresses")

        changed_networks = {
            k: getattr(config, k) for k in ("v4_network", "v6_network")
            if getattr(config, k) != getattr(old_config, k)
        }
        if changed_networks:
            system_ips = await self.middleware.call("interface.ip_in_use", {"static": True})
            system_cidrs = system_ips_to_cidrs(system_ips)
            for k, net_str in changed_networks.items():
                network = ipaddress.ip_network(net_str, strict=False)
                validate_network_overlaps(f"lxc_config_update.{k}", network, system_cidrs, verrors)

        verrors.check()

        await self.middleware.call("datastore.update", self._datastore, old_config.id, config.model_dump())

        return await self.config()
