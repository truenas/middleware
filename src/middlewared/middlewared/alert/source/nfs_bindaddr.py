from middlewared.alert.base import AlertLevel, FilePresenceAlertSource


class NFSBindAlertSource(FilePresenceAlertSource):
    level = AlertLevel.WARNING
    title = "NFS services could not bind specific IPs, using wildcard"

    path = "/tmp/.nfsbindip_notfound"
