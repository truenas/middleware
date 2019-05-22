from middlewared.alert.base import AlertLevel, FilePresenceAlertSource


class ActiveDirectoryDomainBindAlertSource(FilePresenceAlertSource):
    level = AlertLevel.WARNING
    title = "ActiveDirectory Did Not Bind to the Domain"

    path = "/tmp/.adalert"
