# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.alert.base import (
    Alert,
    AlertClass,
    AlertClassConfig,
    AlertCategory,
    AlertLevel,
    AlertSource,
)


class BONDInactivePortsAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.NETWORK,
        level=AlertLevel.CRITICAL,
        title="Ports are Not ACTIVE on BOND Interface",
        text="These ports are not ACTIVE on BOND interface %(name)s: %(ports)s. Please check cabling and switch.",
    )


class BONDNoActivePortsAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.NETWORK,
        level=AlertLevel.CRITICAL,
        title="There are No ACTIVE Ports on BOND Interface",
        text="There are no ACTIVE ports on BOND interface %(name)s. Please check cabling and switch.",
    )


class BONDMissingPortsAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.NETWORK,
        level=AlertLevel.CRITICAL,
        title="BOND Interface references missing ports",
        text="BOND Interface %(name)s references missing ports %(missing)s.",
    )


class BondStatus(AlertSource):
    async def check(self):
        alerts = []
        ifaces = {i["id"]: i for i in await self.middleware.call("interface.query")}
        for iface, info in ifaces.items():
            if info["type"] != "LINK_AGGREGATION":
                continue

            active, inactive, missing = list(), list(), list()
            for member in info["lag_ports"]:
                try:
                    if ifaces[member]["state"]["link_state"] == "LINK_STATE_DOWN":
                        inactive.append(member)
                    else:
                        active.append(member)
                except KeyError:
                    missing.append(member)

            if missing:
                alerts.append(
                    Alert(
                        BONDMissingPortsAlert,
                        {"name": iface, "missing": ", ".join(missing)},
                    )
                )
            elif not active:
                alerts.append(Alert(BONDNoActivePortsAlert, {"name": iface}))
            elif inactive and (info["lag_protocol"] != "FAILOVER" or len(active) == 1):
                # 1. if this isn't FAILOVER type and any inactive
                # 2. OR if it's FAILOVER and we only have 1 active
                # we need to raise an alert
                alerts.append(
                    Alert(
                        BONDInactivePortsAlert,
                        {"name": iface, "ports": ", ".join(inactive)},
                    )
                )

        return alerts
