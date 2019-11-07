from middlewared.alert.base import AlertLevel, FilePresenceAlertSource


class NFSBindAlertSource(FilePresenceAlertSource):
    level = AlertLevel.WARNING
    title = "NFS Services Could Not Bind to Specific IP Addresses, Using 0.0.0.0"

    run_on_backup_node = False

    path = "/tmp/.nfsbindip_notfound"
