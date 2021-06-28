import errno
import os
import shutil

from pkg_resources import parse_version

from middlewared.schema import Bool, Dict, Ref, Str, returns
from middlewared.service import accepts, CallError, job, private, Service

from .utils import get_namespace, run


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @accepts(
        Str('release_name'),
        Dict(
            'rollback_options',
            Bool('force_rollback', default=False),
            Bool('recreate_resources', default=False),
            Bool('rollback_snapshot', default=True),
            Str('item_version', required=True),
        )
    )
    @returns(Ref('chart_release_entry'))
    @job(lock=lambda args: f'chart_release_rollback_{args[0]}')
    async def rollback(self, job, release_name, options):
        """
        Rollback a chart release to a previous chart version.

        `item_version` is version which we want to rollback a chart release to.

        `rollback_snapshot` is a boolean value which when set will rollback snapshots of any PVC's or ix volumes being
        consumed by the chart release.

        `force_rollback` is a boolean which when set will force rollback operation to move forward even if no
        snapshots are found. This is only useful when `rollback_snapshot` is set.

        `recreate_resources` is a boolean which will delete and then create the kubernetes resources on rollback
        of chart release. This should be used with caution as if chart release is consuming immutable objects like
        a PVC, the rollback operation can't be performed and will fail as helm tries to do a 3 way patch for rollback.

        Rollback is functional for the actual configuration of the release at the `item_version` specified and
        any associated `ix_volumes` with any PVC's which were consuming chart release storage class.
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
        force_rollback = options['force_rollback']
        helm_force_flag = options['recreate_resources']

        # If helm force flag is specified, we should see if the chart release is consuming any PVC's and if it is,
        # let's not initiate a rollback as it's destined to fail by helm
        if helm_force_flag and release['resources']['persistent_volume_claims']:
            raise CallError(
                f'Unable to rollback {release_name!r} as chart release is consuming PVC. '
                'Please unset recreate_resources to proceed with rollback.'
            )

        # TODO: Remove the logic for ix_volumes as moving on we would be only snapshotting volumes and only rolling
        #  it back
        snap_data = {'volumes': False, 'volumes/ix_volumes': False}
        for snap in snap_data:
            volumes_ds = os.path.join(release['dataset'], snap)
            snap_name = f'{volumes_ds}@{history_ver}'
            if await self.middleware.call('zfs.snapshot.query', [['id', '=', snap_name]]):
                snap_data[snap] = snap_name

        if options['rollback_snapshot'] and not any(snap_data.values()) and not force_rollback:
            raise CallError(
                f'Unable to locate {", ".join(snap_data.keys())!r} snapshot(s) for {release_name!r} volumes',
                errno=errno.ENOENT
            )

        current_dataset_paths = {
            os.path.join('/mnt', d['id']) for d in await self.middleware.call(
                'zfs.dataset.query', [['id', '^', f'{os.path.join(release["dataset"], "volumes/ix_volumes")}/']]
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
        job.set_progress(45, 'Scaling down workloads')
        scale_stats = await (
            await self.middleware.call('chart.release.scale', release_name, {'replica_count': 0})
        ).wait(raise_error=True)

        job.set_progress(50, 'Rolling back chart release')

        command = []
        if helm_force_flag:
            command.append('--force')

        cp = await run(
            [
                'helm', 'rollback', release_name, history_ver, '-n',
                get_namespace(release_name), '--recreate-pods'
            ] + command, check=False,
        )
        await self.middleware.call('chart.release.sync_secrets_for_release', release_name)

        # Helm rollback is a bit tricky, it utilizes rollout functionality of kubernetes and rolls back the
        # resources to specified version. However in this process, if the rollback is to fail for any reason, it's
        # possible that some k8s resources got rolled back to previous version whereas others did not. We should
        # in this case check if helm treats the chart release as on the previous version of the chart release, we
        # should still do a rollback of snapshots in this case and raise the error afterwards. However if helm
        # does not recognize the chart release on a previous version, we can just raise it right away then.
        current_version = (
            await self.middleware.call('chart.release.get_instance', release_name)
        )['chart_metadata']['version']
        if current_version != rollback_version and cp.returncode:
            raise CallError(
                f'Failed to rollback {release_name!r} chart release to {rollback_version!r}: {cp.stderr.decode()}'
            )

        # We are going to remove old chart version copies
        await self.middleware.call(
            'chart.release.remove_old_upgraded_chart_version_copies',
            os.path.join(release['path'], 'charts'), rollback_version,
        )

        if options['rollback_snapshot'] and any(snap_data.values()):
            for snap_name in filter(bool, snap_data.values()):
                await self.middleware.call(
                    'zfs.snapshot.rollback', snap_name, {
                        'force': True,
                        'recursive': True,
                        'recursive_clones': True,
                        'recursive_rollback': True,
                    }
                )
                break

        await self.middleware.call(
            'chart.release.scale_release_internal', release['resources'], None, scale_stats['before_scale'], True,
        )

        job.set_progress(100, 'Rollback complete for chart release')

        await self.middleware.call('chart.release.chart_releases_update_checks_internal', [['id', '=', release_name]])

        if cp.returncode:
            # This means that helm partially rolled back k8s resources and recognizes the chart release as being
            # on the previous version, we should raise an appropriate exception explaining the behavior
            raise CallError(
                f'Failed to complete rollback {release_name!r} chart release to {rollback_version}. Chart release\'s '
                f'datasets have been rolled back to {rollback_version!r} version\'s snapshot. Errors encountered '
                f'during rollback were: {cp.stderr.decode()}'
            )

        return await self.middleware.call('chart.release.get_instance', release_name)

    @private
    def remove_old_upgraded_chart_version_copies(self, charts_path, current_version):
        c_v = parse_version(current_version)
        for v_path in filter(lambda p: p != current_version, os.listdir(charts_path)):
            if parse_version(v_path) > c_v:
                shutil.rmtree(path=os.path.join(charts_path, v_path), ignore_errors=True)
