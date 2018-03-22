from middlewared.alert.base import AlertLevel, FilePresenceAlertSource


class ActiveDirectoryDomainBindAlertSource(FilePresenceAlertSource):
    level = AlertLevel.WARNING
    title = "ActiveDirectory did not bind to the domain"

    path = "/tmp/.adalert"
