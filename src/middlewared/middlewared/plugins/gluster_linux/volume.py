from gfs.cli import volume
from gfs.cli.utils import GlusterCmdException

from middlewared.service import (CRUDService, accepts,
                                 job, private, ValidationErrors,
                                 CallError)
from middlewared.schema import Dict, Str, Int, Bool, List


class GlusterVolumeService(CRUDService):

    class Config:
        namespace = 'gluster.volume'

    def __volume_wrapper(self, method, args=None, kwargs=None):

        result = b''

        try:
            if args and not kwargs:
                result = method(*args)
            if kwargs and not args:
                result = method(**kwargs)
            if args and kwargs:
                result = method(*args, **kwargs)
            if not args and not kwargs:
                result = method()
        except GlusterCmdException as e:
            rc, out, err = e.args[0]
            err = err if err else out
            raise CallError(f'{err.decode().strip()}')
        except Exception:
            raise

        return result.decode().strip()

    @private
    def common_validation(self, job):

        verrors = ValidationErrors()

        self.validate_gluster_jobs(verrors, job)

    @private
    def validate_gluster_jobs(self, verrors, job):
        """
        When there is another gluster operation ongoing,
        there is a 120 second timeout. During this timeout,
        other gluster related operations will not work and can fail.

        Since this is by design, accommodate for it.
        """

        peer_job = self.middleware.call_sync(
            'core.get_jobs', [
                ['method', '^', 'gluster.peer'],
                ['state', 'in', ['RUNNING']],
            ]
        )

        if peer_job:
            verrors.add(
                'validate_gluster_jobs',
                'There is an ongoing gluster peer operation. '
                'Please wait for it to complete and then try again.'
            )
            raise verrors

        volume_job = self.middleware.call_sync(
            'core.get_jobs', [
                ['method', '^', 'gluster.volume'],
                ['state', 'in', ['RUNNING']],
                ['id', '!=', job.id],
            ]
        )

        if volume_job:
            verrors.add(
                'validate_gluster_jobs',
                'There is an ongoing gluster volume operation. '
                'Please wait for it to complete and then try again.'
            )
            raise verrors

    @private
    def create_volume(self, data):

        volname = data.pop('volname')
        volbricks = data.pop('volbricks')

        bricks = []
        for i in volbricks:
            peer = i.get('peer_name')
            path = i.get('peer_path')
            final = peer + ':' + path
            bricks.append(final)

        args = (volname, bricks)
        kwargs = data

        result = self.__volume_wrapper(volume.create, args, kwargs)

        return result

    @private
    def delete_volume(self, data):

        volname = data.get('volname')

        args = (volname,)

        result = self.__volume_wrapper(volume.delete, args)

        return result

    @private
    def info_volume(self, data):

        volname = data.get('volname')

        if volname:
            args = (volname,)
            result = self.__volume_wrapper(volume.info, args)
        else:
            result = self.__volume_wrapper(volume.info)

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
        Int('replica', default=0),
        Int('stripe', default=0),
        Int('arbiter', default=0),
        Int('disperse', default=0),
        Int('disperse_data', default=0),
        Int('redundancy', default=0),
        Bool('force', default=False),
    ))
    @job(lock='gluster_volume_create')
    def do_create(self, job, data):
        """
        Create a gluster volume.

        `volname` Name to be given to the gluster volume
        `volbricks` List of brick paths for the gluster volume

            `peer_name` IP or DNS name of the peer in the
                trusted storage pool.

            `peer_path` The full path of the dataset to be exported
                for the gluster volume.

        `replica` Number of replica bricks
        `stripe` Number of stripe bricks
        `arbiter` Number of arbiter bricks
        `disperse` Number of disperse bricks
        `disperse_data` Number of disperse data bricks
        `redundancy` Number of redundancy bricks
        `force` Create volume forcefully, ignoring potential warnings
        """

        self.common_validation(job)

        return self.create_volume(data)

    @accepts(Dict(
        'glustervolume_delete',
        Str('volname', required=True)
    ))
    @job(lock='gluster_volume_delete')
    def do_delete(self, job, data):
        """
        Delete a gluster volume.

        `volname` Name of the volume to be deleted
        """

        self.common_validation(job)

        result = self.delete_volume(data)

        return result

    @accepts(Dict(
        'glustervolume_info',
        Str('volname', default='')
    ))
    @job(lock='gluster_volume_info')
    def info(self, job, data):
        """
        Return information about gluster volume(s).
        If a gluster volume name has not been given,
        this will return information about all volumes
        detected in the cluster.

        `volname` Name of the gluster volume
        """

        self.common_validation(job)

        result = self.info_volume(data)

        return result
