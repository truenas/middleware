from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, FilePresenceAlertSource


class ActiveDirectoryDomainBindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "ActiveDirectory did not bind to the domain"


class ActiveDirectoryDomainBindAlertSource(FilePresenceAlertSource):
    path = "/tmp/.adalert"
    klass = ActiveDirectoryDomainBindAlertClass
