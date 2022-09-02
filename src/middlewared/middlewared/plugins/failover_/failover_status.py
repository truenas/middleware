from middlewared.service import Service


class DetectFailoverStatusService(Service):

    class Config:
        private = True
        namespace = 'failover.status'

    async def get_local(self, app):
        licensed = await self.middleware.call('failover.licensed')
        if not licensed:
            # no HA license so nothing else matters
            return 'SINGLE'

        fenced_running = (await self.middleware.call('failover.fenced.run_info'))['running']
        only_boot_pool = len((await self.middleware.call('zfs.pool.query_imported_fast'))) <= 1
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

        master_ifaces = backup_ifaces = 0
        interfaces = await self.middleware.call('interface.query')
        for iface in filter(lambda x: x['state']['vrrp_config'], interfaces):
            for ip in iface['state']['vrrp_config']:
                if ip['state'] == 'MASTER':
                    master_ifaces += 1
                else:
                    backup_ifaces += 1

        if master_ifaces and not backup_ifaces:
            # all interfaces that are configured for HA are master, safe to assume
            # this _should_ be the master node. we shouldn't get here on a
            # healhy HA system because we should be able to determine the status
            # based on zpools and fenced running
            return 'MASTER'
        elif backup_ifaces and not master_ifaces:
            # all interfaces that are configured for HA are backup, safe to assume
            # this _should_ be the backup node. we shouldn't get here on a
            # healhy HA system because we should be able to determine the status
            # based on zpools and fenced running
            return 'BACKUP'

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
