from middlewared.service import Service


class DetectFailoverStatusService(Service):

    class Config:
        private = True
        namespace = 'failover.status'

    async def get_local(self, app):

        # Check if we have at least 1 interface with VRRP config
        interfaces = await self.middleware.call('interface.query')
        if not any(filter(lambda x: x['state']['vrrp_config'], interfaces)):
            return 'SINGLE'

        pools = await self.middleware.call('zfs.pool.query_imported_fast')
        if len(pools) <= 1:
            # Check if we have at least 1 pool configured and imported (excluding boot pool)
            return 'SINGLE'
        elif (await self.middleware.call('failover.vip.get_states', interfaces))[0]:
            # Means we have VRRP MASTER interfaces and we have pool(s) imported
            return 'MASTER'
        else:
            failover_events = await self.middleware.call(
                'core.get_jobs', [('method', '=', 'failover.event.vrrp_master')], {'order_by': ['-id']}
            )
            for i in failover_events:
                if i['state'] == 'RUNNING':
                    # we're currently becoming master node
                    return i['progress']['description']
                elif i['progress']['description'] == 'ERROR':
                    # last failover failed
                    return i['progress']['description']
