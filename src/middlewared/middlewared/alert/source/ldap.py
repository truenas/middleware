from middlewared.alert.base import *


class LDAPAlertSource(FilePresenceAlertSource):
    level = AlertLevel.WARNING
    title = "LDAP did not bind to the domain"

    path = "/tmp/.ldap_status_alert"
