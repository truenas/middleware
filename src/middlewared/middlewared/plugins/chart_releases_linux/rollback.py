import errno
import os
import shutil

from pkg_resources import parse_version

from middlewared.schema import Bool, Dict, Str
from middlewared.service import accepts, CallError, job, private, Service

from .utils import get_namespace, run


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @accepts(
        Str('release_name'),
        Dict(
            'rollback_options',
            Bool('force', default=False),
            Bool('rollback_snapshot', default=True),
            Str('item_version', required=True),
        )
    )
    @job(lock=lambda args: f'chart_release_rollback_{args[0]}')
    async def rollback(self, job, release_name, options):
        """
        Rollback a chart release to a previous chart version.

        `item_version` is version which we want to rollback a chart release to.

        `rollback_snapshot` is a boolean value which when set will rollback snapshots of ix_volumes.

        `force` is a boolean passed to helm for rollback of a chart release and also used for rolling back snapshots
        of ix_volumes.

        It should be noted that rollback is not possible if a chart release is using persistent volume claims
        as they are immutable.
        Rollback is only functional for the actual configuration of the release at the `item_version` specified and
        any associated `ix_volumes`.
        """
        await self.middleware.call('kubernetes.validate_k8s_setup')
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

        history_item = release['history'][rollback_version]
        history_ver = str(history_item['version'])

        ix_volumes_ds = os.path.join(release['dataset'], 'volumes/ix_volumes')
        snap_name = f'{ix_volumes_ds}@{history_ver}'
        if not await self.middleware.call('zfs.snapshot.query', [['id', '=', snap_name]]) and not options['force']:
            raise CallError(
                f'Unable to locate {snap_name!r} snapshot for {release_name!r} volumes', errno=errno.ENOENT
            )

        current_dataset_paths = {
            os.path.join('/mnt', d['id']) for d in await self.middleware.call(
                'zfs.dataset.query', [['id', '^', f'{ix_volumes_ds}/']]
            )
        }
        history_datasets = {d['hostPath'] for d in history_item['config'].get('ixVolumes', [])}
        if history_datasets - current_dataset_paths:
            raise CallError(
                'Please specify a rollback version where following iX Volumes are not being used as they don\'t '
                f'exist anymore: {", ".join(d.split("/")[-1] for d in history_datasets - current_dataset_paths)}'
            )

        job.set_progress(25, 'Initial validation complete')

        # TODO: Upstream helm does not have ability to force stop a release, until we have that ability
        #  let's just try to do a best effort to scale down scaleable workloads and then scale them back up
        scale_stats = await self.middleware.call('chart.release.scale', release_name, {'replica_count': 0})
        job.set_progress(45, 'Scaled down workloads')

        command = []
        if options['force']:
            command.append('--force')

        try:
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
        finally:
            await self.middleware.call('chart.release.sync_secrets_for_release', release_name)

        # We are going to remove old chart version copies
        await self.middleware.call(
            'chart.release.remove_old_upgraded_chart_version_copies',
            os.path.join(release['path'], 'charts'), rollback_version,
        )

        if options['rollback_snapshot']:
            await self.middleware.call(
                'zfs.snapshot.rollback', snap_name, {
                    'force': options['force'],
                    'recursive': True,
                    'recursive_clones': True,
                }
            )

        await self.middleware.call(
            'chart.release.scale_release_internal', release['resources'], None, scale_stats['before_scale'], True,
        )

        job.set_progress(100, 'Rollback complete for chart release')

        await self.middleware.call('chart.release.chart_releases_update_checks_internal', [['id', '=', release_name]])

        return await self.middleware.call('chart.release.get_instance', release_name)

    @private
    def remove_old_upgraded_chart_version_copies(self, charts_path, current_version):
        c_v = parse_version(current_version)
        for v_path in filter(lambda p: p != current_version, os.listdir(charts_path)):
            if parse_version(v_path) > c_v:
                shutil.rmtree(path=os.path.join(charts_path, v_path), ignore_errors=True)
