from middlewared.alert.base import AlertLevel, FilePresenceAlertSource


class LDAPAlertSource(FilePresenceAlertSource):
    level = AlertLevel.WARNING
    title = "LDAP Did Not Bind to the Domain"

    path = "/tmp/.ldap_status_alert"
