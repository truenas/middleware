from middlewared.service import ConfigService, private


class CIFSService(ConfigService):

    def config(self):
        """Returns CIFS configuration object."""
        return self.middleware.call('datastore.config', 'services.cifs', {'extend': 'cifs.cifs_extend'})

    @private
    def cifs_extend(self, cifs):
        """Extend cifs for netbios."""
        if not self.middleware.call('notifier.is_freenas') and self.middleware.call('notifier.failover_node') == 'B':
            cifs['netbiosname'] = cifs['cifs_srv_netbiosname_b']
        else:
            cifs['netbiosname'] = cifs['cifs_srv_netbiosname']
        return cifs
