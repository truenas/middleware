# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.service import Service

MASTER_PRIO = 254
BACKUP_PRIO = 200


class FailoverVrrpService(Service):
    class Config:
        private = True
        cli_private = True
        namespace = 'failover.vrrp'

    def get_priority(self):
        """Return the VRRP priority value that should be set
        based on whether or not this controller is the MASTER
        or BACKUP system"""
        master_event = self.middleware.call_sync('core.get_jobs', [
            ('method', '=', 'failover.events.vrrp_master')
            ('state', '=', 'RUNNING'),
        ])
        fenced = self.middleware.call_sync('failover.fenced.run_info')
        if master_event and fenced['running']:
            # a master event is taking place and it started fenced
            return MASTER_PRIO
        return BACKUP_PRIO
