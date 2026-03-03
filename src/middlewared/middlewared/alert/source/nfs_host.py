from middlewared.alert.base import AlertCategory, AlertClass, AlertClassConfig, AlertLevel, OneShotAlertClass


class NFSHostnameLookupFailAlertClass(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="NFS shares reference hosts that could not be resolved",
        text="NFS shares refer to the following unresolvable hosts: %(hosts)s",
        keys=[],
    )


class NFSHostListExcessiveAlertClass(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="NFS host list excessively long",
        text=(
            "The NFS share, %(sharePath)s, has %(numEntries)d host entries. "
            "A lengthy host list can lead to unexpected failures or performance issues. "
            "Consider using directory services, netgroups, network ranges, "
            "or other configurations to reduce the host list length."
        ),
        keys=[],
    )


class NFSNetworkListExcessiveAlertClass(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="NFS network list excessively long",
        text=(
            "The NFS share, %(sharePath)s, has %(numEntries)d network entries. "
            "A lengthy network list can lead to unexpected failures or performance issues. "
            "Consider using directory services, netgroups, wider network ranges, "
            "or other configurations to reduce the network list length."
        ),
        keys=[],
    )
