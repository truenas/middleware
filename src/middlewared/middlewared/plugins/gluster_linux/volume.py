from glustercli.cli import volume, quota

from middlewared.utils import filter_list
from middlewared.service import CRUDService, accepts, job, filterable, private, ValidationErrors
from middlewared.schema import Dict, Str, Int, Bool, List, Ref, returns
from middlewared.plugins.cluster_linux.utils import CTDBConfig, FuseConfig
from .utils import GlusterConfig, set_gluster_workdir_dataset, get_gluster_workdir_dataset, format_bricks


GLUSTER_JOB_LOCK = GlusterConfig.CLI_LOCK.value
CTDB_VOL_NAME = CTDBConfig.CTDB_VOL_NAME.value
FUSE_BASE = FuseConfig.FUSE_PATH_BASE.value


class GlusterVolumeService(CRUDService):

    class Config:
        datastore_primary_key_type = 'string'
        namespace = 'gluster.volume'
        cli_namespace = 'service.gluster.volume'

    ENTRY = Dict(
        'gluster_volume_entry',
        Str('name'),
        Str('uuid'),
        Str('type'),
        Bool('online'),
        Dict(
            'ports',
            Str('tcp'),
            Str('rdma'),
        ),
        Str('pid'),
        Int('size_total'),
        Int('size_free'),
        Int('size_used'),
        Int('inodes_total'),
        Int('inodes_free'),
        Int('inodes_used'),
        Str('device'),
        Str('block_size'),
        Str('mnt_options'),
        Str('fs_name'),
        additional_attrs=True,
    )

    @filterable
    async def query(self, filters, filter_options):
        vols = []
        if await self.middleware.call('service.started', 'glusterd'):
            method = volume.status_detail
            options = {'kwargs': {'group_subvols': True}}
            vols = await self.middleware.call('gluster.method.run', method, options['kwargs'])
            vols = list(map(lambda i: dict(i, id=i['name']), vols))

        return filter_list(vols, filters, filter_options)

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

    @private
    def store_workdir(self):
        if get_gluster_workdir_dataset() is not None:
            return

        sysdataset = self.middleware.call_sync('systemdataset.config')
        if not sysdataset['basename']:
            self.logger.warning(
                'Systemdataset not properly configured when gluster volume created'
            )
            return

        set_gluster_workdir_dataset(sysdataset['basename'])

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
        bricks = await format_bricks(data.pop('bricks'))
        options = {'args': (name, bricks,), 'kwargs': data}

        await self.middleware.call('gluster.method.run', volume.create, options)
        await self.middleware.call('gluster.volume.start', {'name': name})
        await self.middleware.call('gluster.volume.store_workdir')
        return await self.middleware.call('gluster.volume.query', [('id', '=', name)])

    @accepts(Dict(
        'volume_start',
        Str('name', required=True),
        Bool('force', default=True)
    ))
    @returns()
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

    @accepts(Dict(
        'volume_restart',
        Str('name', required=True),
        Bool('force', default=True)
    ))
    @returns()
    async def restart(self, data):
        """
        Restart a gluster volume.

        `name` String representing name of gluster volume
        `force` Boolean, if True forcefully restart the gluster volume
        """

        options = {'args': (data.pop('name'),), 'kwargs': data}
        return await self.middleware.call('gluster.method.run', volume.restart, options)

    @accepts(Dict(
        'volume_stop',
        Str('name', required=True),
        Bool('force', default=False)
    ))
    @returns()
    async def stop(self, data):
        """
        Stop a gluster volume.

        `name` String representing name of gluster volume
        `force` Boolean, if True forcefully stop the gluster volume
        """
        name = data.pop('name')

        # this will send a request to all peers in the TSP to unmount the FUSE mountpoint
        await self.middleware.call('gluster.localevents.send', {'event': 'VOLUME_STOP', 'name': name, 'forward': True})
        return await self.middleware.call('gluster.method.run', volume.stop, {'args': (name,), 'kwargs': data})

    @accepts(Str('id'))
    @returns()
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
            data = {'event': 'VOLUME_STOP', 'name': id, 'forward': True}
            await self.middleware.call('gluster.localevents.send', data)
            await self.middleware.call('gluster.method.run', volume.delete, args)

    @accepts(Dict(
        'volume_info',
        Str('name', required=True),
    ))
    @returns(List('volumes', items=[Dict(
        'volume',
        Str('name'),
        Str('uuid'),
        Str('type'),
        Str('status'),
        Int('num_bricks'),
        Int('distribute'),
        Int('stripe'),
        Int('replica'),
        Int('disperse'),
        Int('disperse_redundancy'),
        Int('transport'),
        Int('snapshot_count'),
        List('bricks'),
        List('options'),
    )]))
    async def info(self, data):
        """
        Return information about gluster volume(s).

        `name` String representing name of gluster volume
        """
        options = {'kwargs': {'volname': data['name']}}
        return await self.middleware.call('gluster.method.run', volume.info, options)

    @accepts(Dict(
        'volume_status',
        Str('name', required=True),
        Bool('verbose', default=True),
    ))
    @returns(List('volumes', items=[Ref('gluster_volume_entry')]))
    async def status(self, data):
        """
        Return detailed information about gluster volume.

        `name` String representing name of gluster volume
        `verbose` Boolean, If False, only return brick information
        """
        options = {'kwargs': {'volname': data['name'], 'group_subvols': data['verbose']}}
        return await self.middleware.call('gluster.method.run', volume.status_detail, options)

    @accepts()
    @returns(List('volumes', items=[Str('volume')]))
    async def list(self):
        """
        Return list of gluster volumes.
        """
        return await self.middleware.call('gluster.method.run', volume.vollist, {})

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

    @accepts(Dict(
        'volume_optset',
        Str('name', required=True),
        Dict('opts', required=True, additional_attrs=True),
    ))
    @returns()
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

    @accepts(Dict(
        'volume_quota',
        Str('name', required=True),
        Bool('enable', required=True),
    ))
    @returns()
    async def quota(self, data):
        """
        Enable/Disable the quota for a given gluster volume.

        `name` String representing name of gluster volume
        `enable` Boolean, if True enable quota else disable it
        """

        method = quota.enable if data['enable'] else quota.disable
        options = {'args': (data['name'],)}
        return await self.middleware.call('gluster.method.run', method, options)
