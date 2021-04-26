from glustercli.cli import volume, quota

from middlewared.utils import filter_list
from middlewared.service import (CRUDService, accepts, job,
                                 item_method, filterable,
                                 private, ValidationErrors)
from middlewared.schema import Dict, Str, Int, Bool, List
from middlewared.plugins.cluster_linux.utils import CTDBConfig, FuseConfig
from .utils import GlusterConfig


GLUSTER_JOB_LOCK = GlusterConfig.CLI_LOCK.value
CTDB_VOL_NAME = CTDBConfig.CTDB_VOL_NAME.value
FUSE_BASE = FuseConfig.FUSE_PATH_BASE.value


class GlusterVolumeService(CRUDService):

    class Config:
        datastore_primary_key_type = 'string'
        namespace = 'gluster.volume'
        cli_namespace = 'service.gluster.volume'

    @filterable
    async def query(self, filters, options):
        vols = []
        if await self.middleware.call('service.started', 'glusterd'):
            method = volume.status_detail
            options = {'kwargs': {'group_subvols': True}}
            vols = await self.middleware.call('gluster.method.run', method, options['kwargs'])
            vols = list(map(lambda i: dict(i, id=i['name']), vols))

        return filter_list(vols, filters, options)

    @private
    async def exists_and_started(self, vol):
        result = {'name': vol, 'exists': False, 'started': False}
        filters = [('id', '=', vol)]
        for i in await self.middleware.call('gluster.volume.query', filters):
            result['exists'] = True
            result['started'] = i['status'] == 'Started'

        return result

    @private
    async def common_validation(self, data, schema_name):
        verrors = ValidationErrors()
        create_request = schema_name == 'glustervolume_create'

        if data['name'] == CTDB_VOL_NAME and create_request:
            verrors.add(
                f'{schema_name}.{data["name"]}',
                f'"{data["name"]}" is a reserved name. Choose a different volume name.'
            )

        verrors.check()

    @accepts(Dict(
        'glustervolume_create',
        Str('name', required=True),
        List('bricks', items=[
            Dict(
                'brick',
                Str('peer_name', required=True),
                Str('peer_path', required=True),
            ),
        ], required=True),
        Int('replica'),
        Int('arbiter'),
        Int('disperse'),
        Int('disperse_data'),
        Int('redundancy'),
        Bool('force'),
    ))
    @job(lock=GLUSTER_JOB_LOCK)
    async def do_create(self, job, data):
        """
        Create a gluster volume.

        `name` String representing name to be given to the volume
        `bricks` List representing the brick paths
            `peer_name` String representing IP or DNS name of the peer
            `peer_path` String representing the full path of the brick

        `replica` Integer representing number of replica bricks
        `arbiter` Integer representing number of arbiter bricks
        `disperse` Integer representing number of disperse bricks
        `disperse_data` Integer representing number of disperse data bricks
        `redundancy` Integer representing number of redundancy bricks
        `force` Boolean, if True ignore potential warnings
        """

        schema_name = 'glustervolume_create'
        await self.middleware.call('gluster.volume.common_validation', data, schema_name)

        # make sure this is started since it's responsible for sending
        # events for which we act upon (i.e. FUSE mounting)
        await self.middleware.call('service.start', 'glustereventsd')

        # before we create the gluster volume, we need to ensure
        # the ctdb shared volume is setup
        ctdb_job = await self.middleware.call('ctdb.shared.volume.create')
        await ctdb_job.wait(raise_error=True)

        name = data.pop('name')

        bricks = []
        for i in data.pop('bricks'):
            bricks.append(i['peer_name'] + ':' + i['peer_path'])

        options = {'args': (name, bricks,), 'kwargs': data}
        await self.middleware.call('gluster.method.run', volume.create, options)
        await self.middleware.call('gluster.volume.start', {'name': name})

        return await self.middleware.call('gluster.volume.query', [('id', '=', name)])

    @item_method
    @accepts(Dict(
        'volume_start',
        Str('name', required=True),
        Bool('force', default=True)
    ))
    async def start(self, data):
        """
        Start a gluster volume.

        `name` String representing name of gluster volume
        `force` Boolean, if True forcefully start the gluster volume
        """
        name = data.pop('name')
        options = {'args': (name,), 'kwargs': data}
        result = await self.middleware.call('gluster.method.run', volume.start, options)

        # this will send a request to all peers
        # in the TSP to FUSE mount this volume locally
        data = {'event': 'VOLUME_START', 'name': name, 'forward': True}
        await self.middleware.call('gluster.localevents.send', data)

        return result

    @item_method
    @accepts(Dict(
        'volume_restart',
        Str('name', required=True),
        Bool('force', default=True)
    ))
    async def restart(self, data):
        """
        Restart a gluster volume.

        `name` String representing name of gluster volume
        `force` Boolean, if True forcefully restart the gluster volume
        """

        options = {'args': (data.pop('name'),), 'kwargs': data}
        return await self.middleware.call('gluster.method.run', volume.restart, options)

    @item_method
    @accepts(Dict(
        'volume_stop',
        Str('name', required=True),
        Bool('force', default=False)
    ))
    async def stop(self, data):
        """
        Stop a gluster volume.

        `name` String representing name of gluster volume
        `force` Boolean, if True forcefully stop the gluster volume
        """
        name = data.pop('name')
        options = {'args': (name,), 'kwargs': data}
        result = await self.middleware.call('gluster.method.run', volume.stop, options)

        # this will send a request to all peers
        # in the TSP to unmount the FUSE mountpoint
        data = {'event': 'VOLUME_STOP', 'name': name, 'forward': True}
        await self.middleware.call('gluster.localevents.send', data)

        return result

    @accepts(Str('id'))
    @job(lock=GLUSTER_JOB_LOCK)
    async def do_delete(self, job, id):
        """
        Delete a gluster volume.

        `id` String representing name of gluster volume
                to be deleted
        """

        args = {'args': ((await self.get_instance(id))['name'],)}

        if id == CTDB_VOL_NAME:
            # if the ctdb shared volume is being deleted then call
            # the ctdb shared volume specific API since it handles
            # other items
            await (await self.middleware.call('ctdb.shared.volume.delete')).wait(raise_error=True)
        else:
            # need to unmount the FUSE mountpoint (if it exists) and
            # send the request to do the same to all other peers in
            # the TSP before we delete the volume
            data = {'event': 'VOLUME_START', 'name': id, 'forward': True}
            await self.middleware.call('gluster.localevents.send', data)
            await self.middleware.call('gluster.method.run', volume.delete, args)

    @item_method
    @accepts(Dict(
        'volume_info',
        Str('name', required=True),
    ))
    async def info(self, data):
        """
        Return information about gluster volume(s).

        `name` String representing name of gluster volume
        """

        options = {'kwargs': {'volname': data['name']}}
        return await self.middleware.call('gluster.method.run', volume.info, options)

    @item_method
    @accepts(Dict(
        'volume_status',
        Str('name', required=True),
        Bool('verbose', default=True),
    ))
    async def status(self, data):
        """
        Return detailed information about gluster volume.

        `name` String representing name of gluster volume
        `verbose` Boolean, If False, only return brick information
        """

        options = {'kwargs': {'volname': data['name'], 'group_subvols': data['verbose']}}
        return await self.middleware.call('gluster.method.run', volume.status_detail, options)

    @accepts()
    async def list(self):
        """
        Return list of gluster volumes.
        """

        return await self.middleware.call('gluster.method.run', volume.vollist, {})

    @item_method
    @accepts(Dict(
        'volume_optreset',
        Str('name', required=True),
        Str('opt'),
        Bool('force'),
    ))
    async def optreset(self, data):
        """
        Reset volumes options.
            If `opt` is not provided, then all options
            will be reset.

        `name` String representing name of gluster volume
        `opt` String representing name of the option to reset
        `force` Boolean, if True forcefully reset option(s)
        """

        options = {'args': (data.pop('name'),), 'kwargs': data}
        return await self.middleware.call('gluster.method.run', volume.optreset, options)

    @item_method
    @accepts(Dict(
        'volume_optset',
        Str('name', required=True),
        Dict('opts', required=True, additional_attrs=True),
    ))
    async def optset(self, data):
        """
        Set gluster volume options.

        `name` String representing name of gluster volume
        `opts` Dict where
            --key-- is the name of the option
            --value-- is the value to be given to the option
        """

        options = {'args': (data['name'],), 'kwargs': data['opts']}
        return await self.middleware.call('gluster.method.run', volume.optset, options)

    @item_method
    @accepts(Dict(
        'volume_addbrick',
        Str('name', required=True),
        List('bricks', items=[
            Dict(
                'brick',
                Str('peer_name', required=True),
                Str('peer_path', required=True),
            ),
        ], required=True),
        Int('replica'),
        Int('arbiter'),
        Bool('force'),
    ))
    async def addbrick(self, data):
        """
        Add bricks to a gluster volume.

        `name` String representing name of gluster volume
        `bricks` List representing the brick paths
            `peer_name` String representing IP or DNS name of the peer
            `peer_path` String representing the full path of the brick
        `replica` Integer replicating replica count
        `arbiter` Integer replicating arbiter count
        `force` Boolean, if True, forcefully add brick(s)
        """

        bricks = []
        for i in data.pop('bricks'):
            bricks.append(i['peer_name'] + ':' + i['peer_path'])

        options = {'args': (data.pop('name'), bricks,), 'kwargs': data}
        return await self.middleware.call('gluster.method.run', volume.bricks.add, options)

    @item_method
    @accepts(Dict(
        'volume_removebrick',
        Str('name', required=True),
        List('bricks', items=[
            Dict(
                'brick',
                Str('peer_name', required=True),
                Str('peer_path', required=True),
            ),
        ], required=True),
        Str(
            'operation',
            enum=['START', 'STOP', 'COMMIT', 'STATUS', 'FORCE'],
            required=True,
        ),
        Int('replica'),
    ))
    async def removebrick(self, data):
        """
        Perform a remove operation on the brick(s) in the gluster volume.

        `name` String representing name of gluster volume
        `bricks` List representing the brick paths
            `peer_name` String representing IP or DNS name of the peer
            `peer_path` String representing the full path of the brick
        `operation` String representing the operation to be performed
            `START` Start the removal of the brick(s)
            `STOP` Stop the removal of the brick(s)
            `COMMIT` Commit the removal of the brick(s)
            `STATUS` Display status of the removal of the brick(s)
            `FORCE` Force the removal of the brick(s)
        `replica` Integer representing replica count
        """

        op = data.pop('operation')
        name = data.pop('name')
        bricks = []
        for i in data.pop('bricks'):
            bricks.append(i['peer_name'] + ':' + i['peer_path'])

        options = {'args': (name, bricks,), 'kwargs': data}
        if op.lower() == 'start':
            method = volume.bricks.remove_start
        elif op.lower() == 'stop':
            method = volume.bricks.remove_stop
        elif op.lower() == 'commit':
            method = volume.bricks.remove_commit
        elif op.lower() == 'status':
            method = volume.bricks.remove_status
        elif op.lower() == 'force':
            method = volume.bricks.remove_force

        return await self.middleware.call('gluster.method.run', method, options)

    @item_method
    @accepts(Dict(
        'volume_replacebrick',
        Str('name', required=True),
        Dict(
            'src_brick',
            Str('peer_name', required=True),
            Str('peer_path', required=True),
            required=True,
        ),
        Dict(
            'new_brick',
            Str('peer_name', required=True),
            Str('peer_path', required=True),
            required=True,
        ),
    ))
    async def replacebrick(self, data):
        """
        Commit the replacement of a brick.

        `name` String representing name of gluster volume
        `src_brick` Dict where
            `peer_name` key is a string representing IP or DNS name of the peer
            `peer_path` key is a string representing the full path of the brick
        `new_brick` Dict where
            `peer_name` key is a string representing IP or DNS name of the peer
            `peer_path` key is a string representing the full path of the brick
        """

        src = data.pop('src_brick')
        new = data.pop('new_brick')
        src_brick = src['peer_name'] + ':' + src['peer_path']
        new_brick = new['peer_name'] + ':' + new['peer_path']

        method = volume.bricks.replace_commit
        options = {'args': (data.pop('name'), src_brick, new_brick)}
        return await self.middleware.call('gluster.method.run', method, options)

    @item_method
    @accepts(Dict(
        'volume_quota',
        Str('name', required=True),
        Bool('enable', required=True),
    ))
    async def quota(self, data):
        """
        Enable/Disable the quota for a given gluster volume.

        `name` String representing name of gluster volume
        `enable` Boolean, if True enable quota else disable it
        """

        method = quota.enable if data['enable'] else quota.disable
        options = {'args': (data['name'],)}
        return await self.middleware.call('gluster.method.run', method, options)
