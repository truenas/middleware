from gfs.cli import volume
from gfs.cli.utils import GlusterCmdException

from middlewared.service import (CRUDService, accepts,
                                 job, private, CallError)
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
    def create_volume(self, data):

        volname = data.pop('volname')
        volbricks = data.pop('volbricks')

        bricks = []
        for i in volbricks:
            peer = i['peer_name']
            path = i['peer_path']
            brick = peer + ':' + path
            bricks.append(brick)

        result = self.__volume_wrapper(
            volume.create, volname, bricks, **data)

        return result

    @private
    def addbrick_volume(self, data):

        volname = data.pop('volname')
        volbricks = data.pop('bricks')

        bricks = []
        for i in volbricks:
            peer = i['peer_name']
            path = i['peer_path']
            brick = peer + ':' + path
            bricks.append(brick)

        result = self.__volume_wrapper(
            volume.bricks.add, volname, bricks, **data)

        return result

    @private
    def removebrick_volume(self, data):

        volname = data.pop('volname')
        volbricks = data.pop('bricks')
        op = data.pop('operation')

        bricks = []
        for i in volbricks:
            peer = i['peer_name']
            path = i['peer_path']
            brick = peer + ':' + path
            bricks.append(brick)
        # TODO
        # glustercli-python has a bug where if provided the "force"
        # option, it will concatenate it with the "start" option
        # This is wrong, you can choose "start" or "force" exclusively
        # (i.e. gluster volume volname remove-brick peer:path start OR force)
        if op.lower() == 'start':
            result = self.__volume_wrapper(
                volume.bricks.remove_start, volname, bricks, **data)

        if op.lower() == 'stop':
            result = self.__volume_wrapper(
                volume.bricks.remove_stop, volname, bricks, **data)

        if op.lower() == 'commit':
            result = self.__volume_wrapper(
                volume.bricks.remove_commit, volname, bricks, **data)

        if op.lower() == 'status':
            result = self.__volume_wrapper(
                volume.bricks.remove_status, volname, bricks, **data)

        return result

    @private
    def replacebrick_volume(self, data):

        volname = data.pop('volname')
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
            volname,
            src_brick,
            new_brick,
            **data)

        return result

    @accepts(Dict(
        'glustervolume_create',
        Str('volname', required=True),
        List('volbricks', items=[
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

        `volname` Name to be given to the gluster volume
        `volbricks` List of brick paths
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

        return self.create_volume(data)

    @accepts(Dict(
        'glustervolume_start',
        Str('volname', required=True),
        Bool('force'),
    ))
    @job(lock=GLUSTER_JOB_LOCK)
    def start(self, job, data):
        """
        Start a gluster volume.

        `volname` Name of gluster volume
        `force` Forcefully start the gluster volume
        """

        volname = data.pop('volname')

        result = self.__volume_wrapper(volume.start, volname, **data)

        return result

    @accepts(Dict(
        'glustervolume_restart',
        Str('volname', required=True),
        Bool('force'),
    ))
    @job(lock=GLUSTER_JOB_LOCK)
    def restart(self, job, data):
        """
        Restart a gluster volume.

        `volname` Name of gluster volume
        `force` Forcefully restart the gluster volume
        """

        volname = data.pop('volname')

        result = self.__volume_wrapper(volume.restart, volname, **data)

        return result

    @accepts(Dict(
        'glustervolume_stop',
        Str('volname', required=True),
        Bool('force'),
    ))
    @job(lock=GLUSTER_JOB_LOCK)
    def stop(self, job, data):
        """
        Stop a gluster volume.

        `volname` Name of gluster volume
        `force` Forcefully stop the gluster volume
        """

        volname = data.pop('volname')

        result = self.__volume_wrapper(volume.stop, volname, **data)

        return result

    @accepts(Dict(
        'glustervolume_delete',
        Str('volname', required=True),
    ))
    @job(lock=GLUSTER_JOB_LOCK)
    def do_delete(self, job, data):
        """
        Delete a gluster volume.

        `volname` Name of the volume to be deleted
        """

        result = self.__volume_wrapper(volume.delete, data['volname'])

        return result

    @accepts(Dict(
        'glustervolume_info',
        Str('volname')
    ))
    @job(lock=GLUSTER_JOB_LOCK)
    def info(self, job, data):
        """
        Return information about gluster volume(s).
        If a gluster volume name has not been given,
        this will return information about all volumes
        detected in the cluster.

        `volname` Name of the gluster volume
        """

        result = self.__volume_wrapper(volume.info, **data)

        return result

    @accepts(Dict(
        'glustervolume_status',
        Str('volname')
    ))
    @job(lock=GLUSTER_JOB_LOCK)
    def status(self, job, data):
        """
        Return detailed information about gluster volume(s).
        If a gluster volume name has not been given,
        this will return detailed information about all volumes
        detected in the cluster.

        `volname` Name of the gluster volume
        """

        result = self.__volume_wrapper(volume.status_detail, **data)

        return result

    @accepts()
    @job(lock=GLUSTER_JOB_LOCK)
    def list(self, job):
        """
        Return list of gluster volumes.
        """

        result = self.__volume_wrapper(volume.vollist)

        return result

    @accepts(Dict(
        'glustervolume_optreset',
        Str('volname', required=True),
        Str('opt'),
        Bool('force'),
    ))
    @job(lock=GLUSTER_JOB_LOCK)
    def optreset(self, job, data):
        """
        Reset volumes options.
            If `opt` is not provided, then all options
            will be reset.

        `volname` Name of the gluster volume
        `opt` Name of the option to reset
        `force` Forcefully reset option(s)
        """

        volname = data.pop('volname')

        result = self.__volume_wrapper(volume.optreset, volname, **data)

        return result

    @accepts(Dict(
        'glustervolume_optset',
        Str('volname', required=True),
        Dict('opts', required=True, additional_attrs=True),
    ))
    @job(lock=GLUSTER_JOB_LOCK)
    def optset(self, job, data):
        """
        Set gluster volume options.

        `volname` Name of the gluster volume
        `opts` Dict where
            --key-- is the name of the option
            --value-- is the value to be given to the option
        """

        volname = data.pop('volname')

        result = self.__volume_wrapper(volume.optset, volname, **data)

        return result

    @accepts(Dict(
        'glustervolume_addbrick',
        Str('volname', required=True),
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
    ))
    @job(lock=GLUSTER_JOB_LOCK)
    def addbrick(self, job, data):
        """
        Add bricks to a gluster volume.

        `volname` Gluster volume name
        `bricks` List of brick paths.
            `peer_name` IP or DNS name of the peer
            `peer_path` The full path of the brick to be added

        `stripe` Stripe count
        `repica` Replica count
        `arbiter` Arbiter count
        `force` Forcefully add brick(s)
        """

        result = self.addbrick_volume(data)

        return result

    @accepts(Dict(
        'glustervolume_removebrick',
        Str('volname', required=True),
        List('bricks', items=[
            Dict(
                'brick',
                Str('peer_name', required=True),
                Str('peer_path', required=True),
            ),
        ], required=True),
        Str('operation', enum=['START', 'STOP', 'COMMIT', 'STATUS'], required=True),
        Int('replica'),
    ))
    @job(lock=GLUSTER_JOB_LOCK)
    def removebrick(self, job, data):
        """
        Perform a remove operation on the brick(s) in the gluster volume.

        `volname` Gluster volume name
        `bricks` List of brick paths.
            `peer_name` IP or DNS name of the peer
            `peer_path` The full path of the brick

        `operation` The operation to be performed
            `START` Start the removal of the brick(s)
            `STOP` Stop the removal of the brick(s)
            `COMMIT` Commit the removal of the brick(s)
            `STATUS` Display status of the removal of the brick(s)

        `repica` Replica count
        `force` Forcefully run the removal operation.
        """

        result = self.removebrick_volume(data)

        return result

    @accepts(Dict(
        'glustervolume_replacebrick',
        Str('volname', required=True),
        Dict(
            'src_brick',
            Str('peer_name', required=True),
            Str('peer_path', required=True),
        ),
        Dict(
            'new_brick',
            Str('peer_name', required=True),
            Str('peer_path', required=True),
        ),
        Bool('force'),
    ))
    @job(lock=GLUSTER_JOB_LOCK)
    def replacebrick(self, job, data):
        """
        Commit the replacement of a brick.

        `volname` Gluster volume name
        `src_brick` Brick to be replaced
            `peer_name` IP or DNS name of the peer
            `peer_path` The full path of the brick

        `new_brick` New replacement brick
            `peer_name` IP or DNS name of the peer
            `peer_path` The full path of the brick

        `force` Forcefully replace bricks
        """

        result = self.replacebrick_volume(data)

        return result
