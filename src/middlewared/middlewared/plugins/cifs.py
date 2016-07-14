from middlewared.service import Service
from OpenSSL import crypto

import dateutil
import dateutil.parser
import logging
import os
import re

class CIFSService(Service):

    def query(self, filters=None, options=None):
        if options is None:
            options = {}
        options['extend'] = 'cifs.cifs_extend'
        return self.middleware.call('datastore.query', 'services.cifs', filters, options)

    def cifs_extend(self, cifs):
        """Extend cifs for netbios

        @private
        """
        if not self.middleware.call('notifier.is_freenas') and self.middleware.call('notifier.failover_node') == 'B':
            cifs['netbiosname'] = cifs['cifs_srv_netbiosname_b']
        else:
            cifs['netbiosname'] = cifs['cifs_srv_netbiosname']
        return cifs
