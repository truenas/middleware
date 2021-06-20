import asyncio
import copy
import errno
import json
import os
import shutil
import subprocess
import tempfile

from pkg_resources import parse_version

from middlewared.schema import Bool, Dict, Ref, Str, returns
from middlewared.service import accepts, CallError, job, periodic, private, Service, ValidationErrors

from .schema import clean_values_for_upgrade
from .utils import CONTEXT_KEY_NAME, get_action_context, SCALEABLE_RESOURCES, SCALE_DOWN_ANNOTATION


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def scale_down_workloads_before_snapshot(self, job, release):
        resources = []
        pod_mapping = await self.middleware.call('chart.release.get_workload_to_pod_mapping', release['namespace'])
        pods_to_watch_for = []
        for resource in SCALEABLE_RESOURCES:
            for workload in await self.middleware.call(
                f'k8s.{resource.name.lower()}.query', [
                    [f'metadata.annotations.{SCALE_DOWN_ANNOTATION["key"]}', 'in',
                     SCALE_DOWN_ANNOTATION['value']],
                    ['metadata.namespace', '=', release['namespace']],
                ]
            ):
                resources.append({
                    'replica_count': 0,
                    'type': resource.name,
                    'name': workload['metadata']['name'],
                })
                pods_to_watch_for.extend(pod_mapping[workload['metadata']['uid']])

        if not resources:
            return

        job.set_progress(35, f'Scaling down {", ".join([r["name"] for r in resources])} workload(s)')
        await self.middleware.call('chart.release.scale_workloads', release['id'], resources)
        await self.middleware.call(
            'chart.release.wait_for_pods_to_terminate', release['namespace'], [
                ['metadata.name', 'in', pods_to_watch_for],
            ]
        )
        job.set_progress(40, 'Successfully scaled down workload(s)')

    @accepts(
        Str('release_name'),
        Dict(
            'upgrade_options',
            Dict('values', additional_attrs=True),
            Str('item_version', default='latest'),
        )
    )
    @returns(Ref('chart_release_entry'))
    @job(lock=lambda args: f'chart_release_upgrade_{args[0]}')
    async def upgrade(self, job, release_name, options):
        """
        Upgrade `release_name` chart release.

        `upgrade_options.item_version` specifies to which item version chart release should be upgraded to.

        System will update container images being used by `release_name` chart release as a chart release
        upgrade is not considered complete until the images in use have also been updated to latest versions.

        During upgrade, `upgrade_options.values` can be specified to apply configuration changes for configuration
        changes for the chart release in question.

        When chart version is upgraded, system will automatically take a snapshot of `ix_volumes` in question
        which can be used to rollback later on.
        """
        await self.middleware.call('kubernetes.validate_k8s_setup')
        release = await self.middleware.call('chart.release.get_instance', release_name)
        if not release['update_available'] and not release['container_images_update_available']:
            raise CallError('No update is available for chart release')

        # We need to update container images before upgrading chart version as it's possible that the chart version
        # in question needs newer image hashes.
        job.set_progress(10, 'Updating container images')
        await (
            await self.middleware.call('chart.release.pull_container_images', release_name, {'redeploy': False})
        ).wait(raise_error=True)
        job.set_progress(30, 'Updated container images')

        await self.scale_down_workloads_before_snapshot(job, release)

        # If a snapshot of the volumes already exist with the same name in case of a failed upgrade, we will remove
        # it as we want the current point in time being reflected in the snapshot
        # TODO: Remove volumes/ix_volumes check in next release as we are going to do a recursive snapshot
        #  from parent volumes ds moving on
        for filesystem in ('volumes', 'volumes/ix_volumes'):
            volumes_ds = os.path.join(release['dataset'], filesystem)
            snap_name = f'{volumes_ds}@{release["version"]}'
            if await self.middleware.call('zfs.snapshot.query', [['id', '=', snap_name]]):
                await self.middleware.call('zfs.snapshot.delete', snap_name, {'recursive': True})

        await self.middleware.call(
            'zfs.snapshot.create', {
                'dataset': os.path.join(release['dataset'], 'volumes'), 'name': release['version'], 'recursive': True
            }
        )
        job.set_progress(50, 'Created snapshot for upgrade')

        if release['update_available']:
            await self.upgrade_chart_release(job, release, options)
        else:
            await (await self.middleware.call('chart.release.redeploy', release_name)).wait(raise_error=True)

        chart_release = await self.middleware.call('chart.release.get_instance', release_name)
        self.middleware.send_event('chart.release.query', 'CHANGED', id=release_name, fields=chart_release)

        await self.chart_releases_update_checks_internal([['id', '=', release_name]])

        job.set_progress(100, 'Upgrade complete for chart release')

        return chart_release

    @accepts(
        Str('release_name'),
        Dict(
            'options',
            Str('item_version', default='latest', empty=False)
        )
    )
    @returns(Dict(
        Dict(
            'container_images_to_update', additional_attrs=True,
            description='Dictionary of container image(s) which have an update available against the same tag',
        ),
        Str('latest_version'),
        Str('latest_human_version'),
        Str('changelog', max_length=None, null=True),
    ))
    def upgrade_summary(self, release_name, options):
        """
        Retrieve upgrade summary for `release_name` which will include which container images will be updated
        and changelog for `options.item_version` chart version specified if applicable. If only container images
        need to be updated, changelog will be `null`.

        If chart release `release_name` does not require an upgrade, an error will be raised.
        """
        release = self.middleware.call_sync(
            'chart.release.query', [['id', '=', release_name]], {'extra': {'retrieve_resources': True}, 'get': True}
        )
        if not release['update_available'] and not release['container_images_update_available']:
            raise CallError('No update is available for chart release', errno=errno.ENOENT)

        latest_version = release['chart_metadata']['version']
        latest_human_version = release['human_version']
        changelog = None
        if release['update_available']:
            catalog_item = self.middleware.call_sync('chart.release.get_version', release, options)
            latest_version = catalog_item['version']
            latest_human_version = catalog_item['human_version']
            changelog = catalog_item['changelog']

        return {
            'container_images_to_update': {
                k: v for k, v in release['resources']['container_images'].items() if v['update_available']
            },
            'latest_version': latest_version,
            'latest_human_version': latest_human_version,
            'changelog': changelog,
        }

    @private
    async def get_version(self, release, options):
        current_chart = release['chart_metadata']
        chart = current_chart['name']
        item_details = await self.middleware.call('catalog.get_item_details', chart, {
            'catalog': release['catalog'],
            'train': release['catalog_train'],
        })

        new_version = options['item_version']
        if new_version == 'latest':
            new_version = await self.middleware.call(
                'chart.release.get_latest_version_from_item_versions', item_details['versions']
            )

        if new_version not in item_details['versions']:
            raise CallError(f'Unable to locate specified {new_version!r} item version.')

        verrors = ValidationErrors()
        if parse_version(new_version) <= parse_version(current_chart['version']):
            verrors.add(
                'upgrade_options.item_version',
                f'Upgrade version must be greater than {current_chart["version"]!r} current version.'
            )

        verrors.check()

        return item_details['versions'][new_version]

    @private
    async def upgrade_chart_release(self, job, release, options):
        release_orig = copy.deepcopy(release)
        release_name = release['name']

        catalog_item = await self.get_version(release, options)
        await self.middleware.call('catalog.version_supported_error_check', catalog_item)

        config = await self.middleware.call('chart.release.upgrade_values', release, catalog_item['location'])

        # We will be performing validation for values specified. Why we want to allow user to specify values here
        # is because the upgraded catalog item version might have different schema which potentially means that
        # upgrade won't work or even if new k8s are resources are created/deployed, they won't necessarily function
        # as they should because of changed params or expecting new params
        # One tricky bit which we need to account for first is removing any key from current configured values
        # which the upgraded release will potentially not support. So we can safely remove those as otherwise
        # validation will fail as new schema does not expect those keys.
        config = clean_values_for_upgrade(config, catalog_item['schema']['questions'])
        config.update(options['values'])

        config, context = await self.middleware.call(
            'chart.release.normalise_and_validate_values', catalog_item, config, False, release['dataset'],
            release_orig,
        )
        job.set_progress(50, 'Initial validation complete for upgrading chart version')

        # We have validated configuration now

        chart_path = os.path.join(release['path'], 'charts', catalog_item['version'])
        await self.middleware.run_in_thread(shutil.rmtree, chart_path, ignore_errors=True)
        await self.middleware.run_in_thread(shutil.copytree, catalog_item['location'], chart_path)

        await self.middleware.call('chart.release.perform_actions', context)

        # Let's update context options to reflect that an upgrade is taking place and from which version to which
        # version it's happening.
        # Helm considers simple config change as an upgrade as well, and we have no way of determining the old/new
        # chart versions during helm upgrade in the helm template, hence the requirement for a context object.
        config[CONTEXT_KEY_NAME].update({
            **get_action_context(release_name),
            'operation': 'UPGRADE',
            'isUpgrade': True,
            'upgradeMetadata': {
                'oldChartVersion': release['chart_metadata']['version'],
                'newChartVersion': catalog_item['version'],
                'preUpgradeRevision': release['version'],
            }
        })

        job.set_progress(60, 'Upgrading chart release version')

        await self.middleware.call('chart.release.helm_action', release_name, chart_path, config, 'upgrade')

    @private
    def upgrade_values(self, release, new_version_path):
        config = copy.deepcopy(release['config'])
        chart_version = release['chart_metadata']['version']
        migration_path = os.path.join(new_version_path, 'migrations')
        migration_files = [os.path.join(migration_path, k) for k in (f'migrate_from_{chart_version}', 'migrate')]
        if not os.path.exists(migration_path) or all(not os.access(p, os.X_OK) for p in migration_files):
            return config

        # This is guaranteed to exist based on above check
        file_path = next(f for f in migration_files if os.access(f, os.X_OK))

        with tempfile.NamedTemporaryFile(mode='w+') as f:
            f.write(json.dumps(config))
            f.flush()
            cp = subprocess.Popen([file_path, f.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = cp.communicate()

        if cp.returncode:
            raise CallError(f'Failed to apply migration: {stderr.decode()}')

        if stdout:
            # We add this as a safety net in case something went wrong with the migration and we get a null response
            # or the chart dev mishandled something - although we don't suppress any exceptions which might be raised
            config = json.loads(stdout.decode())

        return config

    @periodic(interval=86400)
    @private
    async def periodic_chart_releases_update_checks(self):
        sync_job = await self.middleware.call('catalog.sync_all')
        await sync_job.wait()
        if not await self.middleware.call('service.started', 'kubernetes'):
            return

        await self.chart_releases_update_checks_internal()

    @private
    async def chart_releases_update_checks_internal(self, chart_releases_filters=None):
        chart_releases_filters = chart_releases_filters or []
        # Chart release wrt alerts will be considered valid for upgrade/update if either there's a newer
        # catalog item version available or any of the images it's using is outdated

        catalog_items = {
            f'{c["id"]}_{train}_{item}': c['trains'][train][item]
            for c in await self.middleware.call('catalog.query', [], {'extra': {'item_details': True}})
            for train in c['trains'] for item in c['trains'][train]
        }
        for application in await self.middleware.call('chart.release.query', chart_releases_filters):
            if application['container_images_update_available']:
                await self.middleware.call('alert.oneshot_create', 'ChartReleaseUpdate', application)
                continue

            app_id = f'{application["catalog"]}_{application["catalog_train"]}_{application["chart_metadata"]["name"]}'
            catalog_item = catalog_items.get(app_id)
            if not catalog_item:
                continue

            await self.chart_release_update_check(catalog_item, application)

        container_config = await self.middleware.call('container.config')
        if container_config['enable_image_updates']:
            asyncio.ensure_future(self.middleware.call('container.image.check_update'))

    @private
    async def chart_release_update_check(self, catalog_item, application):
        latest_version = catalog_item['latest_version']
        if not latest_version:
            return

        if parse_version(latest_version) > parse_version(application['chart_metadata']['version']):
            await self.middleware.call('alert.oneshot_create', 'ChartReleaseUpdate', application)
        else:
            await self.middleware.call('alert.oneshot_delete', 'ChartReleaseUpdate', application['id'])

    @accepts(
        Str('release_name'),
        Dict(
            'pull_container_images_options',
            Bool('redeploy', default=True),
        )
    )
    @returns(Dict(
        'container_images', additional_attrs=True,
        description='Dictionary of container image(s) with container image tag as key and update status as value',
        example={
            'plexinc/pms-docker:1.23.2.4656-85f0adf5b': 'Updated image',
        }
    ))
    @job(lock=lambda args: f'pull_container_images{args[0]}')
    async def pull_container_images(self, job, release_name, options):
        """
        Update container images being used by `release_name` chart release.

        `redeploy` when set will redeploy pods which will result in chart release using newer updated versions of
        the container images.
        """
        await self.middleware.call('kubernetes.validate_k8s_setup')
        images = [
            {'orig_tag': tag, 'from_image': tag.rsplit(':', 1)[0], 'tag': tag.rsplit(':', 1)[-1]}
            for tag in (await self.middleware.call(
                'chart.release.query', [['id', '=', release_name]],
                {'extra': {'retrieve_resources': True}, 'get': True}
            ))['resources']['container_images']
        ]
        results = {}

        bulk_job = await self.middleware.call(
            'core.bulk', 'container.image.pull', [
                [{'from_image': image['from_image'], 'tag': image['tag']}]
                for image in images
            ]
        )
        await bulk_job.wait()
        if bulk_job.error:
            raise CallError(f'Failed to update container images for {release_name!r} chart release: {bulk_job.error}')

        for tag, status in zip(images, bulk_job.result):
            if status['error']:
                results[tag['orig_tag']] = f'Failed to pull image: {status["error"]}'
            else:
                results[tag['orig_tag']] = 'Updated image'

        if options['redeploy']:
            await job.wrap(await self.middleware.call('chart.release.redeploy', release_name))

        return results

    @private
    async def clear_update_alerts_for_all_chart_releases(self):
        for chart_release in await self.middleware.call('chart.release.query'):
            await self.middleware.call('alert.oneshot_delete', 'ChartReleaseUpdate', chart_release['id'])
