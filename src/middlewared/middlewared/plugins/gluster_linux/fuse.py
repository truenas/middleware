from pathlib import Path

from middlewared.utils import run
from middlewared.service import (Service, CallError, job,
                                 accepts, Dict, Str, Bool,
                                 ValidationErrors, private)
from middlewared.plugins.cluster_linux.utils import FuseConfig


FUSE_BASE = FuseConfig.FUSE_PATH_BASE.value


class GlusterFuseService(Service):

    class Config:
        namespace = 'gluster.fuse'
        cli_namespace = 'service.gluster.fuse'

    @accepts(Dict(
        'glusterfuse_mounted',
        Str('name', required=True),
    ))
    async def is_mounted(self, data):
        """
        Check if gluster volume is FUSE mounted locally.

        `name` String representing name of the gluster volume
        """
        path = Path(FUSE_BASE).joinpath(data['name'])
        try:
            mounted = path.is_mount()
        except Exception:
            # can happen when mounted but glusterd service
            # isn't functioning
            mounted = False

        return mounted

    @private
    async def common_validation(self, data, schema_name):
        name = data.get('name', None)
        all_vols = data.get('all', None)

        verrors = ValidationErrors()
        if not name and not all_vols:
            verrors.add(
                f'{schema_name}',
                'A gluster volume name is rquired or the "all" key must be set to True'
            )

        verrors.check()

    @accepts(Dict(
        'gluserfuse_mount',
        Str('name', default=None),
        Bool('all', default=False),
        Bool('raise', default=False),
    ))
    @job(lock='glusterfuse')
    async def mount(self, job, data):
        """
        Mount a gluster volume using the gluster FUSE client.

        `name` String representing the name of the gluster volume
        `all` Boolean if True locally FUSE mount all detected
                gluster volumes
        `raise` Boolean if True raise a CallError if the FUSE mount
                fails
        """
        schema_name = 'glusterfuse.mount'
        await self.middleware.call(
            'gluster.fuse.common_validation', data, schema_name
        )

        filters = [] if data['all'] else [('id', '=', data['name'])]
        vols = await self.middleware.call('gluster.volume.query', filters)
        mounted = []
        if vols:
            # we have to stop the glustereventsd service because when the volume is mounted
            # it triggers an event which then gets processed by middlewared and calls this
            # method again....
            # Furthermore, there is a scenario which can cause a mount/umount loop. If the
            # shared volume is in a self-heal situation because, say, 1 of the peers is down.
            # when we `mount -t glusterfs`, 2 events get generated with identical timestamps.
            # There is nothing we can do about the events and since the timestamps are in
            # seconds (which means they appear at the "same" time), then you can get into a
            # really bad loop. In the above scenario, when mounting a AFR_SUBVOLS_DOWN event
            # is generated and an AFR_SUBVOL_UP event is generated and they both have the same
            # timestamp. Well, according to testing, the SUBVOLS_DOWN event comes "first"
            # while the SUBVOL_UP event comes "second". This means on SUBVOLS_DOWN event, we
            # call the `gluster.volume.umount` method which generates another `SUBVOLS_DOWN`
            # method and because we processed a `SUBVOL_UP` event, we run this method which
            # generates another SUBVOL_UP event........This causes a mount/umount loop.
            # So, as an easy work-around we stop the glusterevevntsd service which prevents
            # any more events from being triggered while we mount/umount the volume.
            await self.middleware.call('service.stop', 'glustereventsd')
            for i in vols:
                try:
                    j = await self.middleware.call('gluster.volume.exists_and_started', i['name'])
                    if j['exists'] and j['started']:
                        path = Path(FUSE_BASE).joinpath(j['name'])
                        try:
                            # make sure the dirs are there
                            path.mkdir(parents=True, exist_ok=True)
                        except Exception as e:
                            raise CallError(f'Failed creating {path} with error: {e}')

                        local_path = Path('localhost:/').joinpath(j['name'])
                        cmd = ['mount', '-t', 'glusterfs', str(local_path), str(path)]
                        cp = await run(cmd, check=False)
                        if cp.returncode:
                            errmsg = cp.stderr.decode().strip()
                            ignore1 = 'is already mounted'
                            if ignore1 in errmsg:
                                mounted.append(True)
                            else:
                                if data['raise']:
                                    raise CallError(
                                        f'Failed to mount {path} with error: {errmsg}'
                                    )
                                else:
                                    self.logger.error(
                                        'Failed to mount %s with error: %s', path, errmsg
                                    )
                                    mounted.append(False)
                        else:
                            mounted.append(True)
                except Exception as e:
                    if data['raise']:
                        raise CallError(e)
                    else:
                        self.logger.error('Unhandled exception', exc_info=True)
                        continue

            # always start it back up
            await self.middleware.call('service.start', 'glustereventsd')

        return all(mounted) if mounted else bool(mounted)

    @accepts(Dict(
        'glusterfuse_umount',
        Str('name', default=None),
        Bool('all', default=False),
        Bool('raise', default=False),
    ))
    @job(lock='glusterfuse')
    async def umount(self, job, data):
        """
        Unmount a locally FUSE mounted gluster volume.

        `name` String representing the name of the gluster volume
        `all` Boolean if True umount all locally detected FUSE
                mounted gluster volumes
        `raise` Boolean if True raise a CallError if the FUSE mount
                fails
        """
        schema_name = 'glusterfuse.umount'
        await self.middleware.call(
            'gluster.fuse.common_validation', data, schema_name
        )

        filters = [] if data['all'] else [('id', '=', data['name'])]
        vols = await self.middleware.call('gluster.volume.query', filters)
        umounted = []
        if vols:
            # see commemt above on why we do this
            await self.middleware.call('service.stop', 'glustereventsd')
            for i in vols:
                path = Path(FUSE_BASE).joinpath(i['name'])
                try:
                    cp = await run(['umount', '-R', str(path)], check=False)
                    if cp.returncode:
                        errmsg = cp.stderr.decode().strip()
                        ignore1 = 'not mounted'
                        ignore2 = i['name'] + ': not found'
                        if ignore1 in errmsg or ignore2 in errmsg:
                            umounted.append(True)
                        else:
                            if data['raise']:
                                raise CallError(
                                    f'Failed to umount {path} with error: {errmsg}'
                                )
                            else:
                                self.logger.error(
                                    'Failed to umount %s with error: %s', path, errmsg
                                )
                                umounted.append(False)
                    else:
                        umounted.append(True)
                except Exception as e:
                    if data['raise']:
                        raise CallError(f'Unhandled exception trying to umount {path}: {e}')
                    else:
                        self.logger.error(
                            'Unhandled exception trying to umount %s', path, exc_info=True
                        )
                        continue

            # always start it back up
            await self.middleware.call('service.start', 'glustereventsd')

        return all(umounted) if umounted else bool(umounted)
