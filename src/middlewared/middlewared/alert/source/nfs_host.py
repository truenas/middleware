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
        "A lengthy host list can lead to unexpected failures or performance issues. "
        "Consider using directory services, netgroups, network ranges, "
        "or other configurations to reduce the host list length."
    )

    async def delete(self, alerts, query):
        return []


class NFSNetworkListExcessiveAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "NFS network list excessively long"
    text = (
        "The NFS share, %(sharePath)s, has %(numEntries)d network entries. "
        "A lengthy network list can lead to unexpected failures or performance issues. "
        "Consider using directory services, netgroups, wider network ranges, "
        "or other configurations to reduce the network list length."
    )

    async def delete(self, alerts, query):
        return []
