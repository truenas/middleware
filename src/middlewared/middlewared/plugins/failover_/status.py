# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.service import Service
from middlewared.utils.zfs import query_imported_fast_impl


class DetectFailoverStatusService(Service):

    class Config:
        private = True
        namespace = 'failover.status'

    async def get_local(self, app):
        licensed = await self.middleware.call('failover.licensed')
        if not licensed:
            # no HA license so nothing else matters
            return 'SINGLE'

        master_ifaces = backup_ifaces = vips_configured = 0
        interfaces = await self.middleware.call('interface.query')
        for iface in filter(lambda x: x['state']['vrrp_config'], interfaces):
            vips_configured += len(iface.get('failover_virtual_aliases', []))
            if iface['state']['vrrp_config']:
                for ip in iface['state']['vrrp_config']:
                    if ip['state'] == 'MASTER':
                        master_ifaces += 1
                    else:
                        backup_ifaces += 1

        if not vips_configured:
            # We have a license but we don't have a single interface that has been
            # configured with a VIP. It's safe to assume that this is a system that
            # has just been licensed for HA. To allow the user to login to the system
            # for initial HA configuration, we need to return SINGLE.
            # `failover.disabled.reasons` will reports lots of issues on why HA isn't
            # "healthy" in this scenario
            return 'SINGLE'
        elif master_ifaces and not backup_ifaces:
            # all interfaces that are configured for HA are master, safe to assume
            # this _should_ be the master node
            return 'MASTER'
        elif backup_ifaces and not master_ifaces:
            # all interfaces that are configured for HA are backup, safe to assume
            # this _should_ be the backup node
            return 'BACKUP'

        fenced_running = (await self.middleware.call('failover.fenced.run_info'))['running']
        only_boot_pool = await self.middleware.run_in_thread(query_imported_fast_impl)
        only_boot_pool = len(only_boot_pool) <= 1
        if not fenced_running:
            if only_boot_pool:
                # we only have boot pool, fenced is not running, and we're licensed
                # safe to assume we're the backup node
                return 'BACKUP'
            else:
                # we have at least 1 zpool imported, but fenced is not running and we're licensed
                # ...that's not good but it's safe to return MASTER. failover.disabled.reasons
                # will return NO_FENCED will cause alerts and warnings and emails to be sent to
                # end-user
                return 'MASTER'
        elif not only_boot_pool:
            # we have at least 1 zpool imported, fenced is running, and we're licensed
            # safe to assume we're the master node
            return 'MASTER'

        # last ditch effort to determine the status of this node. if there are
        # no failover events occurring locally and we make it this far, the caller
        # of this method will check the remote system which is slow...but have no
        # option at that point. Note: we shouldn't get here ideally because calling
        # core.get_jobs is not known for being "performant" especially as more jobs
        # accumulate as uptime increases
        filters = [('method', '=', 'failover.event.vrrp_master')]
        options = {'order_by': ['-id']}
        for i in await self.middleware.call('core.get_jobs', filters, options):
            if i['state'] == 'RUNNING':
                # we're currently becoming master node
                return i['progress']['description']
            elif i['progress']['description'] == 'ERROR':
                # last failover failed
                return i['progress']['description']
