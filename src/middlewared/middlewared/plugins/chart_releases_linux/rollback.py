import errno
import os

from middlewared.schema import Bool, Dict, Str
from middlewared.service import accepts, CallError, Service

from .utils import get_namespace, run


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @accepts(
        Str('release_name'),
        Dict(
            'rollback_options',
            Bool('force', default=False),
            Str('item_version', required=True),
        )
    )
    async def rollback(self, release_name, options):
        release = await self.middleware.call(
            'chart.release.query', [['id', '=', release_name]], {
                'extra': {'history': True, 'retrieve_resources': True}, 'get': True,
            }
        )
        rollback_version = options['item_version']
        if rollback_version not in release['history']:
            raise CallError(
                f'Unable to find {rollback_version!r} item version in {release_name!r} history', errno=errno.ENOENT
            )

        chart_path = os.path.join(release['path'], 'charts', rollback_version)
        if not await self.middleware.run_in_thread(lambda: os.path.exists(chart_path)):
            raise CallError(f'Unable to locate {chart_path!r} path for rolling back', errno=errno.ENOENT)

        chart_details = await self.middleware.call('catalog.item_version_details', chart_path)
        await self.middleware.call('catalog.version_supported_error_check', chart_details)

        ix_volumes_ds = os.path.join(release['dataset'], 'volumes/ix_volumes')
        snap_name = f'{ix_volumes_ds}@{rollback_version}'
        if not await self.middleware.call('zfs.snapshot.query', [['id', '=', snap_name]]) and not options['force']:
            raise CallError(
                f'Unable to locate {snap_name!r} snapshot for {release_name!r} volumes', errno=errno.ENOENT
            )

        history_item = release['history'][rollback_version]
        current_dataset_paths = {
            os.path.join('/mnt', d['id']) for d in await self.middleware.call(
                'pool.dataset.query', [['id', '^', f'{ix_volumes_ds}/']]
            )
        }
        history_datasets = {d['hostPath'] for d in history_item['config'].get('ixVolumes', [])}
        if history_datasets - current_dataset_paths:
            raise CallError(
                'Please specify a rollback version where following iX Volumes are not being used as they don\'t '
                f'exist anymore: {", ".join(d.split("/")[-1] for d in history_datasets - current_dataset_paths)}'
            )

        history_ver = str(history_item['version'])

        # TODO: Upstream helm does not have ability to force stop a release, until we have that ability
        #  let's just try to do a best effort to scale down scaleable workloads and then scale them back up
        scale_stats = await self.middleware.call('chart.release.scale', release_name, {'replica_count': 0})

        command = []
        if options['force']:
            command.append('--force')

        cp = await run(
            [
                'helm', 'rollback', release_name, history_ver, '-n',
                get_namespace(release_name), '--recreate-pods'
            ] + command, check=False,
        )
        if cp.returncode:
            raise CallError(
                f'Failed to rollback {release_name!r} chart release to {rollback_version!r}: {cp.stderr.decode()}'
            )

        await self.middleware.call(
            'zfs.snapshot.rollback', snap_name, {
                'force': options['force'],
                'recursive': True,
                'recursive_clones': True,
            }
        )

        await self.middleware.call(
            'chart.release.scale_release_internal', release['resources'], None, scale_stats['before_scale']
        )

        return await self.middleware.call('chart.release.get_instance', release_name)
