from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, FilePresenceAlertSource


class LDAPAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "LDAP did not bind to the domain"


class LDAPAlertSource(FilePresenceAlertSource):
    path = "/tmp/.ldap_status_alert"
    klass = LDAPAlertClass
