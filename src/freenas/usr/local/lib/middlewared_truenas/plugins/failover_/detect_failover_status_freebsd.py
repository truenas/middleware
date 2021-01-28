import os

from middlewared.service import Service


class DetectFailoverStatusService(Service):

    class Config:
        private = True
        namespace = 'failover.status'

    async def get_local(self, app):

        # Check if we have at least 1 interface with CARP config
        interfaces = await self.middleware.call('interface.query')
        if not any(filter(lambda x: x['state']['carp_config'], interfaces)):
            return 'SINGLE'

        # Check if we have at least 1 pool configured and imported
        pools = await self.middleware.call('pool.query')
        if not pools:
            return 'SINGLE'

        # Check if we have any CARP MASTER interfaces
        masters = (await self.middleware.call('failover.vip.get_states', interfaces))[0]
        if masters:
            # If we have CARP MASTER interfaces, ensure none of the zpools
            # are offline
            if any(filter(lambda x: x.get('status') != 'OFFLINE', pools)):
                return 'MASTER'

            # Check for failover related sentinels
            # (eventually remove these and use cache/keyvalue store?)
            if os.path.exists('/tmp/.failover_electing'):
                return 'ELECTING'
            if os.path.exists('/tmp/.failover_importing'):
                return 'IMPORTING'
            if os.path.exists('/tmp/.failover_failed'):
                return 'ERROR'
