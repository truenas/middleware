import ipaddress

from middlewared.api import api_method
from middlewared.api.current import (
    LXCConfigEntry,
    LXCConfigUpdateArgs, LXCConfigUpdateResult,
    LXCConfigBridgeChoicesArgs, LXCConfigBridgeChoicesResult,
)
from middlewared.service import ConfigService, ValidationErrors
from middlewared.utils.network import system_ips_to_cidrs, validate_network_overlaps
import middlewared.sqlalchemy as sa


BRIDGE_AUTO = '[AUTO]'


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


class LXCConfigService(ConfigService):

    class Config:
        cli_namespace = "service.lxc.config"
        datastore = "container_config"
        namespace = "lxc"
        role_prefix = "LXC_CONFIG"
        entry = LXCConfigEntry

    @api_method(
        LXCConfigUpdateArgs,
        LXCConfigUpdateResult,
        audit='LXC configuration update'
    )
    async def do_update(self, data):
        """
        Update container config.
        """
        old_config = await self.config()
        config = old_config.copy()
        config.update(data)

        if config["bridge"] in ("", BRIDGE_AUTO):
            config["bridge"] = None

        verrors = ValidationErrors()

        if (config["bridge"] or BRIDGE_AUTO) not in await self.bridge_choices():
            verrors.add("lxc_config_update.bridge", "Invalid bridge")

        if config["bridge"] is None and config["v4_network"] is None and config["v6_network"] is None:
            verrors.add(
                "lxc_config_update.bridge",
                "You must specify either IPv4 network of IPv6 network for automatically-configured bridge"
            )

        if config["preferred_pool"]:
            await self.middleware.call(
                "container.validate_pool", verrors, "lxc_config_update.preferred_pool", config["preferred_pool"]
            )

        for k in ["v4_network", "v6_network"]:
            if config[k]:
                if ipaddress.ip_interface(config[k]).network.num_addresses < 4:
                    verrors.add(f"lxc_config_update.{k}", "The network must have at least 4 addresses")

        changed_networks = {
            k: config[k] for k in ("v4_network", "v6_network")
            if config[k] and config[k] != old_config.get(k)
        }
        if changed_networks:
            system_ips = await self.middleware.call("interface.ip_in_use", {"static": True})
            system_cidrs = system_ips_to_cidrs(system_ips)
            for k, net_str in changed_networks.items():
                network = ipaddress.ip_network(net_str, strict=False)
                validate_network_overlaps(f"lxc_config_update.{k}", network, system_cidrs, verrors)

        verrors.check()

        await self.middleware.call("datastore.update", self._config.datastore, old_config["id"], config)

        return await self.config()

    @api_method(LXCConfigBridgeChoicesArgs, LXCConfigBridgeChoicesResult, roles=["LXC_CONFIG_READ"])
    async def bridge_choices(self):
        """
        Bridge choices for virtualization purposes.

        Empty means it will be managed/created automatically.
        """
        choices = {BRIDGE_AUTO: "Automatic"}
        # We do not allow custom bridge on HA because it might have bridge STP issues
        # causing failover problems.
        if not await self.middleware.call("failover.licensed"):
            choices.update({
                i["name"]: i["name"]
                for i in await self.middleware.call("interface.query", [["type", "=", "BRIDGE"]])
            })

        return choices
