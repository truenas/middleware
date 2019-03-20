from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, FilePresenceAlertSource


class NFSBindAlertClass(AlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "NFS services could not bind specific IPs, using wildcard"


class NFSBindAlertSource(FilePresenceAlertSource):
    path = "/tmp/.nfsbindip_notfound"
    klass = NFSBindAlertClass
