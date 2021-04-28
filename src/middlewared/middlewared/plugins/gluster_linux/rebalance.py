from glustercli.cli import rebalance

from middlewared.service import accepts, Service, job
from middlewared.schema import Dict, Str, Bool


LOCK = 'rebalance_lock'


class GlusterRebalanceService(Service):

    class Config:
        namespace = 'gluster.rebalance'
        cli_namespace = 'service.gluster.rebalance'

    @accepts(Dict(
        'rebalance_status',
        Str('name', required=True),
    ))
    @job(lock=LOCK)
    async def status(self, job, data):
        """
        Return the status of a rebalance operation
        for a given gluster volume.

        `name` String representing the gluster volume.
        """
        data = {'args': (data.pop('name'),)}
        method = rebalance.status
        return await self.middleware.call('gluster.method.run', method, data)

    @accepts(Dict(
        'rebalance_fix_layout',
        Str('name', required=True),
    ))
    @job(lock=LOCK)
    async def fix_layout(self, job, data):
        """
        Start a fix-layout operation for a given
        gluster volume.

        `name` String representing the gluster volume.
        """
        data = {'args': (data.pop('name'),)}
        method = rebalance.fix_layout_start
        return await self.middleware.call('gluster.method.run', method, data)

    @accepts(Dict(
        'rebalance_start',
        Str('name', required=True),
        Bool('force', default=False),
    ))
    @job(lock=LOCK)
    async def start(self, job, data):
        """
        Start a rebalance operation for a given
        gluster volume.

        `name` String representing the gluster volume.
        `force` Boolean, when True will forcefully
                start the rebalance operation.
        """
        options = {
            'args': (data.pop('name'),),
            'kwargs': {'force': True} if data.pop('force', False) else {},
        }
        method = rebalance.start
        return await self.middleware.call('gluster.method.run', method, options)

    @accepts(Dict(
        'rebalance_stop',
        Str('name', required=True),
    ))
    @job(lock=LOCK)
    async def stop(self, job, data):
        """
        Stop a rebalance operation for a given
        gluster volume.

        `name` String representing the gluster volume.
        """
        data = {'args': (data.pop('name'),)}
        method = rebalance.stop
        return await self.middleware.call('gluster.method.run', method, data)
