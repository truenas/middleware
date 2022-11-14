from glustercli.cli.bricks import add as bricks_add

from middlewared.service import Service, accepts, job
from middlewared.schema import Dict, Str, List
from .utils import format_bricks


class GlusterBricksService(Service):

    class Config:
        namespace = 'gluster.bricks'
        cli_namespace = 'system.gluster.brick'
        private = True

    @accepts(Dict(
        'add_bricks',
        Str('name', required=True),
        List('bricks', items=[
            Dict(
                'brick',
                Str('peer_name', required=True),
                Str('peer_path', required=True),
            )
        ], required=True),
    ))
    @job(lock='add-bricks')
    async def add(self, job, data):
        """
        Add `bricks` to an existing gluster volume named `name`. This is a private endpoint
        and is expected to only be called via a public facing endpoint since this doesn't do
        any validation. The callers are expected to validate the data before calling this.

        `name` str: name of existing gluster volume.
        `bricks` list of dicts
            `peer_name` str: ip address or hostname of peer in the TSP
            `peer_path` str: absolute path of the brick on `peer_name`
        """
        job.set_progress(50, 'Formatting brick information')
        options = {'args': (data['name'], await format_bricks(data['bricks']),), 'kwargs': {'force': True}}
        job.set_progress(99, f'Adding bricks to {data["name"]!r}')
        await self.middleware.call('gluster.method.run', bricks_add, options)
        job.set_progress(100, f'Bricks successfully added to {data["name"]!r}')
        return await self.middleware.call('gluster.volume.info', {'name': data['name']})
