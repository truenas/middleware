from middlewared.service import Service


class CIFSService(Service):

    def config(self):
        return self.middleware.call('datastore.query', 'services.cifs', None, {'get': True, 'extend': 'cifs.cifs_extend'})

    def cifs_extend(self, cifs):
        """Extend cifs for netbios

        @private
        """
        if not self.middleware.call('notifier.is_freenas') and self.middleware.call('notifier.failover_node') == 'B':
            cifs['netbiosname'] = cifs['cifs_srv_netbiosname_b']
        else:
            cifs['netbiosname'] = cifs['cifs_srv_netbiosname']
        return cifs
