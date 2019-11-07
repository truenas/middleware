from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, FilePresenceAlertSource


class NFSBindAlertClass(AlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "NFS Services Could Not Bind to Specific IP Addresses, Using 0.0.0.0"
    text = "NFS services could not bind to specific IP addresses, using 0.0.0.0."


class NFSBindAlertSource(FilePresenceAlertSource):
    path = "/tmp/.nfsbindip_notfound"
    klass = NFSBindAlertClass

    run_on_backup_node = False
