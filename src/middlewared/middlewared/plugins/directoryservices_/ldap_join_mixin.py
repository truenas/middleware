from middlewared.utils.directoryservices.constants import DSType


class LDAPJoinMixin:
    def _ldap_activate(self) -> None:
        for etc_file in DSType.LDAP.etc_files:
            self.middleware.call_sync('etc.generate', etc_file)

        ds_config = self.middleware.call_sync('directoryservices.config')

        self.middleware.call_sync('service.control', 'STOP', 'sssd').wait_sync(raise_error=True)
        self.middleware.call_sync('service.control', 'START', 'sssd', {'silent': False}).wait_sync(raise_error=True)

        if ds_config['kerberos_realm']:
            self.middleware.call_sync('kerberos.start')
