from glustercli.cli import volume
from glustercli.cli.utils import GlusterCmdException

from middlewared.service import (CRUDService, accepts,
                                 job, private, CallError,
                                 item_method)
from middlewared.schema import Dict, Str, Int, Bool, List

from .utils import GLUSTER_JOB_LOCK


class GlusterVolumeService(CRUDService):

    class Config:
        namespace = 'gluster.volume'

    def __volume_wrapper(self, method, *args, **kwargs):

        result = b''

        try:
            result = method(*args, **kwargs)
        except GlusterCmdException as e:
            rc, out, err = e.args[0]
            err = err if err else out
            raise CallError(f'{err.decode().strip()}')

        if isinstance(result, bytes):
            return result.decode().strip()

        return result

    @private
    def removebrick_volume(self, name, data):

        temp = data.pop('bricks')
        op = data.pop('operation')

        bricks = []
        for i in temp:
            peer = i['peer_name']
            path = i['peer_path']
            brick = peer + ':' + path
            bricks.append(brick)
        # TODO
        # glustercli-python has a bug where if provided the "force"
        # option, it will concatenate it with the "start" option
        # This is wrong, you can choose "start" or "force" exclusively
        # (i.e. gluster volume name remove-brick peer:path start OR force)
        if op.lower() == 'start':
            result = self.__volume_wrapper(
                volume.bricks.remove_start, name, bricks, **data)

        if op.lower() == 'stop':
            result = self.__volume_wrapper(
                volume.bricks.remove_stop, name, bricks, **data)

        if op.lower() == 'commit':
            result = self.__volume_wrapper(
                volume.bricks.remove_commit, name, bricks, **data)

        if op.lower() == 'status':
            result = self.__volume_wrapper(
                volume.bricks.remove_status, name, bricks, **data)

        return result

    @private
    def replacebrick_volume(self, name, data):

        src = data.pop('src_brick')
        new = data.pop('new_brick')

        src_peer = src['peer_name']
        src_path = src['peer_path']
        src_brick = src_peer + ':' + src_path

        new_peer = new['peer_name']
        new_path = new['peer_path']
        new_brick = new_peer + ':' + new_path

        result = self.__volume_wrapper(
            volume.bricks.replace_commit,
            name,
            src_brick,
            new_brick,
            **data)

        return result

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
        Int('stripe'),
        Int('arbiter'),
        Int('disperse'),
        Int('disperse_data'),
        Int('redundancy'),
        Bool('force'),
    ))
    @job(lock=GLUSTER_JOB_LOCK)
    def do_create(self, job, data):
        """
        Create a gluster volume.

        `name` Name to be given to the gluster volume
        `bricks` List of brick paths
            `peer_name` IP or DNS name of the peer.
            `peer_path` The full path of the brick

        `replica` Number of replica bricks
        `stripe` Number of stripe bricks
        `arbiter` Number of arbiter bricks
        `disperse` Number of disperse bricks
        `disperse_data` Number of disperse data bricks
        `redundancy` Number of redundancy bricks
        `force` Create volume forcefully, ignoring potential warnings
        """

        name = data.pop('name')
        temp = data.pop('bricks')

        bricks = []
        for i in temp:
            peer = i['peer_name']
            path = i['peer_path']
            brick = peer + ':' + path
            bricks.append(brick)

        return self.__volume_wrapper(
            volume.create, name, bricks, **data)

    @item_method
    @accepts(
        Str('name', required=True),
        Dict(
            'data',
            Bool('force')
        ),
    )
    @job(lock=GLUSTER_JOB_LOCK)
    def start(self, job, name, data):
        """
        Start a gluster volume.

        `name` Name of gluster volume
        `force` Forcefully start the gluster volume
        """

        result = self.__volume_wrapper(volume.start, name, **data)

        return result

    @item_method
    @accepts(
        Str('name', required=True),
        Dict(
            'data',
            Bool('force')
        ),
    )
    @job(lock=GLUSTER_JOB_LOCK)
    def restart(self, job, name, data):
        """
        Restart a gluster volume.

        `name` Name of gluster volume
        `force` Forcefully restart the gluster volume
        """

        result = self.__volume_wrapper(volume.restart, name, **data)

        return result

    @item_method
    @accepts(
        Str('name', required=True),
        Dict(
            'data',
            Bool('force')
        ),
    )
    @job(lock=GLUSTER_JOB_LOCK)
    def stop(self, job, name, data):
        """
        Stop a gluster volume.

        `name` Name of gluster volume
        `force` Forcefully stop the gluster volume
        """

        result = self.__volume_wrapper(volume.stop, name, **data)

        return result

    @accepts(Dict(
        'glustervolume_delete',
        Str('name', required=True),
    ))
    @job(lock=GLUSTER_JOB_LOCK)
    def do_delete(self, job, data):
        """
        Delete a gluster volume.

        `name` Name of the volume to be deleted
        """

        result = self.__volume_wrapper(volume.delete, data['name'])

        return result

    @item_method
    @accepts(Str('name'))
    @job(lock=GLUSTER_JOB_LOCK)
    def info(self, job, name):
        """
        Return information about gluster volume(s).

        `name` Name of the gluster volume
        """

        rv = {}
        rv['volname'] = name

        result = self.__volume_wrapper(volume.info, **rv)

        return result

    @item_method
    @accepts(Str('name'))
    @job(lock=GLUSTER_JOB_LOCK)
    def status(self, job, name):
        """
        Return detailed information about gluster volume(s).

        `name` Name of the gluster volume
        """

        rv = {}
        rv['volname'] = name

        result = self.__volume_wrapper(volume.status_detail, **rv)

        return result

    @accepts()
    @job(lock=GLUSTER_JOB_LOCK)
    def list(self, job):
        """
        Return list of gluster volumes.
        """

        result = self.__volume_wrapper(volume.vollist)

        return result

    @item_method
    @accepts(
        Str('name', required=True),
        Dict(
            'data',
            Str('opt'),
            Bool('force'),
        )
    )
    @job(lock=GLUSTER_JOB_LOCK)
    def optreset(self, job, name, data):
        """
        Reset volumes options.
            If `opt` is not provided, then all options
            will be reset.

        `name` Name of the gluster volume
        `opt` Name of the option to reset
        `force` Forcefully reset option(s)
        """

        result = self.__volume_wrapper(volume.optreset, name, **data)

        return result

    @item_method
    @accepts(
        Str('name', required=True),
        Dict('opts', required=True, additional_attrs=True),
    )
    @job(lock=GLUSTER_JOB_LOCK)
    def optset(self, job, name, data):
        """
        Set gluster volume options.

        `name` Name of the gluster volume
        `opts` Dict where
            --key-- is the name of the option
            --value-- is the value to be given to the option
        """

        result = self.__volume_wrapper(volume.optset, name, **data)

        return result

    @item_method
    @accepts(
        Str('name', required=True),
        Dict(
            'data',
            List('bricks', items=[
                Dict(
                    'brick',
                    Str('peer_name', required=True),
                    Str('peer_path', required=True),
                ),
            ], required=True),
            Int('stripe'),
            Int('replica'),
            Int('arbiter'),
            Bool('force'),
        )
    )
    @job(lock=GLUSTER_JOB_LOCK)
    def addbrick(self, job, name, data):
        """
        Add bricks to a gluster volume.

        `name` Gluster volume name
        `bricks` List of brick paths.
            `peer_name` IP or DNS name of the peer
            `peer_path` The full path of the brick to be added

        `stripe` Stripe count
        `replica` Replica count
        `arbiter` Arbiter count
        `force` Forcefully add brick(s)
        """

        temp = data.pop('bricks')

        bricks = []
        for i in temp:
            peer = i['peer_name']
            path = i['peer_path']
            brick = peer + ':' + path
            bricks.append(brick)

        return self.__volume_wrapper(
            volume.bricks.add, name, bricks, **data)

    @item_method
    @accepts(
        Str('name', required=True),
        Dict(
            'data',
            List('bricks', items=[
                Dict(
                    'brick',
                    Str('peer_name', required=True),
                    Str('peer_path', required=True),
                ),
            ], required=True),
            Str('operation', enum=['START', 'STOP', 'COMMIT', 'STATUS'], required=True),
            Int('replica'),
        )
    )
    @job(lock=GLUSTER_JOB_LOCK)
    def removebrick(self, job, name, data):
        """
        Perform a remove operation on the brick(s) in the gluster volume.

        `name` Gluster volume name
        `bricks` List of brick paths.
            `peer_name` IP or DNS name of the peer
            `peer_path` The full path of the brick

        `operation` The operation to be performed
            `START` Start the removal of the brick(s)
            `STOP` Stop the removal of the brick(s)
            `COMMIT` Commit the removal of the brick(s)
            `STATUS` Display status of the removal of the brick(s)

        `replica` Replica count
        `force` Forcefully run the removal operation.
        """

        result = self.removebrick_volume(name, data)

        return result

    @item_method
    @accepts(
        Str('name', required=True),
        Dict(
            'data',
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
            Bool('force'),
        )
    )
    @job(lock=GLUSTER_JOB_LOCK)
    def replacebrick(self, job, name, data):
        """
        Commit the replacement of a brick.

        `name` Gluster volume name
        `src_brick` Brick to be replaced
            `peer_name` IP or DNS name of the peer
            `peer_path` The full path of the brick

        `new_brick` New replacement brick
            `peer_name` IP or DNS name of the peer
            `peer_path` The full path of the brick

        `force` Forcefully replace bricks
        """

        result = self.replacebrick_volume(name, data)

        return result
