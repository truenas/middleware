from middlewared.alert.base import AlertLevel, FilePresenceAlertSource


class ActiveDirectoryDomainBindAlertSource(FilePresenceAlertSource):
    level = AlertLevel.WARNING
    title = "Active Directory Did Not Bind to the Domain"

    path = "/tmp/.adalert"
