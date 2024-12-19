from middlewared.alert.base import (
    Alert,
    AlertClass,
    AlertCategory,
    AlertLevel,
    AlertSource,
)


class BONDInactivePortsAlertClass(AlertClass):
    category = AlertCategory.NETWORK
    level = AlertLevel.CRITICAL
    title = "Ports are Not ACTIVE on BOND Interface"
    text = "These ports are not ACTIVE on BOND interface %(name)s: %(ports)s. Please check cabling and switch."


class BONDNoActivePortsAlertClass(AlertClass):
    category = AlertCategory.NETWORK
    level = AlertLevel.CRITICAL
    title = "There are No ACTIVE Ports on BOND Interface"
    text = "There are no ACTIVE ports on BOND interface %(name)s. Please check cabling and switch."


class BONDMissingPortsAlertClass(AlertClass):
    category = AlertCategory.NETWORK
    level = AlertLevel.CRITICAL
    title = "BOND Interface references missing ports"
    text = "BOND Interface %(name)s references missing ports %(missing)s."


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
                    if ifaces[member]["link_state"] == "LINK_STATE_DOWN":
                        inactive.append(member)
                    else:
                        active.append(member)
                except KeyError:
                    missing.append(member)

            if missing:
                alerts.append(
                    Alert(
                        BONDMissingPortsAlertClass,
                        {"name": iface["id"], "missing": ", ".join(missing)},
                    )
                )
            elif not active:
                alerts.append(Alert(BONDNoActivePortsAlertClass, {"name": iface["id"]}))
            elif inactive and (iface["lag_protocol"] != "FAILOVER" or len(active) == 1):
                # 1. if this isn't FAILOVER type and any inactive
                # 2. OR if it's FAILOVER and we only have 1 active
                # we need to raise an alert
                alerts.append(
                    Alert(
                        BONDInactivePortsAlertClass,
                        {"name": iface["id"], "ports": ", ".join(inactive)},
                    )
                )

        return alerts
