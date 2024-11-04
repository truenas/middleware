from middlewared.utils.directoryservices.constants import DSType


class LDAPJoinMixin:
    def _ldap_activate(self) -> None:
        for etc_file in DSType.LDAP.etc_files:
            self.middleware.call_sync('etc.generate', etc_file)

        ldap_config = self.middleware.call_sync('directoryservices.config')['configuration']

        self.middleware.call_sync('service.stop', 'sssd')
        self.middleware.call_sync('service.start', 'sssd', {'silent': False})

        if ldap_config['kerberos_realm']:
            self.middleware.call_sync('kerberos.start')
