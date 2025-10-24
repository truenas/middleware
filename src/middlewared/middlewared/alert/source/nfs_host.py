from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass


class NFSHostnameLookupFailAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "NFS shares reference hosts that could not be resolved"
    text = "NFS shares refer to the following unresolvable hosts: %(hosts)s"

    async def delete(self, alerts, query):
        return []


class NFSHostListExcessiveAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "NFS host list excessively long"
    text = (
        "The NFS share, %(sharePath)s, has %(numEntries)d host entries. "
        "An excessively long list of host entries may lead to "
        "unexpected behavior, performance issues or failures. "
        "If possible, please consider using a directory service, netgroups, "
        "network ranges, or similar to reduce the length of the host list."
    )

    async def delete(self, alerts, query):
        return []


class NFSNetworkListExcessiveAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "NFS network list excessively long"
    text = (
        "The NFS share, %(sharePath)s, has %(numEntries)d network entries. "
        "An excessively long list of network entries may lead to "
        "unexpected behavior, performance issues or failures. "
        "If possible, please consider using a directory service, netgroups, "
        "wider network ranges, or similar to reduce the length of the network list."
    )

    async def delete(self, alerts, query):
        return []
