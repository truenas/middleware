import asyncio
import errno
import os
import shutil
import tempfile
import yaml

from pkg_resources import parse_version

from middlewared.schema import Dict, Str
from middlewared.service import accepts, CallError, job, periodic, private, Service, ValidationErrors

from .schema import clean_values_for_upgrade
from .utils import CONTEXT_KEY_NAME, get_namespace, run


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @accepts(
        Str('release_name'),
        Dict(
            'upgrade_options',
            Dict('values', additional_attrs=True),
            Str('item_version', default='latest'),
        )
    )
    @job(lock=lambda args: f'chart_release_upgrade_{args[0]}')
    async def upgrade(self, job, release_name, options):
        """
        Upgrade `release_name` chart release.

        `upgrade_options.item_version` specifies to which item version chart release should be upgraded to.

        During upgrade, `upgrade_options.values` can be specified to apply configuration changes for configuration
        changes for the chart release in question.

        For upgrade, system will automatically take a snapshot of `ix_volumes` in question which can be used to
        rollback later on.
        """
        release = await self.middleware.call('chart.release.get_instance', release_name)
        catalog = await self.middleware.call(
            'catalog.query', [['id', '=', release['catalog']]], {'get': True, 'extra': {'item_details': True}},
        )
        # TODO: Add a catalog branch check as well when we add support for different catalogs / catalog branches

        current_chart = release['chart_metadata']
        chart = current_chart['name']
        if release['catalog_train'] not in catalog['trains']:
            raise CallError(
                f'Unable to locate {release["catalog_train"]!r} catalog train in {release["catalog"]!r}',
                errno=errno.ENOENT,
            )
        if chart not in catalog['trains'][release['catalog_train']]:
            raise CallError(
                f'Unable to locate {chart!r} catalog item in {release["catalog"]!r} '
                f'catalog\'s {release["catalog_train"]!r} train.', errno=errno.ENOENT
            )

        new_version = options['item_version']
        if new_version == 'latest':
            new_version = await self.middleware.call(
                'chart.release.get_latest_version_from_item_versions',
                catalog['trains'][release['catalog_train']][chart]['versions']
            )

        if new_version not in catalog['trains'][release['catalog_train']][chart]['versions']:
            raise CallError(f'Unable to locate specified {new_version!r} item version.')

        verrors = ValidationErrors()
        if parse_version(new_version) <= parse_version(current_chart['version']):
            verrors.add(
                'upgrade_options.item_version',
                f'Upgrade version must be greater than {current_chart["version"]!r} current version.'
            )

        verrors.check()

        catalog_item = catalog['trains'][release['catalog_train']][chart]['versions'][new_version]
        await self.middleware.call('catalog.version_supported_error_check', catalog_item)

        # We will be performing validation for values specified. Why we want to allow user to specify values here
        # is because the upgraded catalog item version might have different schema which potentially means that
        # upgrade won't work or even if new k8s are resources are created/deployed, they won't necessarily function
        # as they should because of changed params or expecting new params
        # One tricky bit which we need to account for first is removing any key from current configured values
        # which the upgraded release will potentially not support. So we can safely remove those as otherwise
        # validation will fail as new schema does not expect those keys.
        config = clean_values_for_upgrade(release['config'], catalog_item['schema']['questions'])
        config.update(options['values'])

        config, context = await self.middleware.call(
            'chart.release.normalise_and_validate_values', catalog_item, config, False, release['dataset'],
        )
        job.set_progress(25, 'Initial validation complete')

        # We have validated configuration now

        chart_path = os.path.join(release['path'], 'charts', new_version)
        await self.middleware.run_in_thread(shutil.rmtree, chart_path, ignore_errors=True)
        await self.middleware.run_in_thread(shutil.copytree, catalog_item['location'], chart_path)

        # If a snapshot of the volumes already exist with the same name in case of a failed upgrade, we will remove
        # it as we want the current point in time being reflected in the snapshot
        volumes_ds = os.path.join(release['dataset'], 'volumes/ix_volumes')
        snap_name = f'{volumes_ds}@{release["version"]}'
        if await self.middleware.call('zfs.snapshot.query', [['id', '=', snap_name]]):
            await self.middleware.call('zfs.snapshot.delete', snap_name)

        await self.middleware.call(
            'zfs.snapshot.create', {'dataset': volumes_ds, 'name': release['version'], 'recursive': True}
        )
        job.set_progress(40, 'Created snapshot for upgrade')

        await self.middleware.call('chart.release.perform_actions', context)

        # Let's update context options to reflect that an upgrade is taking place and from which version to which
        # version it's happening.
        # Helm considers simple config change as an upgrade as well, and we have no way of determining the old/new
        # chart versions during helm upgrade in the helm template, hence the requirement for a context object.
        config[CONTEXT_KEY_NAME].update({
            'operation': 'UPGRADE',
            'isUpgrade': True,
            'upgradeMetadata': {
                'oldChartVersion': current_chart['version'],
                'newChartVersion': new_version,
                'preUpgradeRevision': release['version'],
            }
        })

        with tempfile.NamedTemporaryFile(mode='w+') as f:
            f.write(yaml.dump(config))
            f.flush()

            cp = await run(
                ['helm', 'upgrade', release_name, chart_path, '-n', get_namespace(release_name), '-f', f.name],
                check=False,
            )
            if cp.returncode:
                raise CallError(f'Failed to upgrade chart release to {new_version!r}: {cp.stderr.decode()}')

        job.set_progress(100, 'Upgrade complete for chart release')

        chart_release = await self.middleware.call('chart.release.get_instance', release_name)
        await self.chart_release_update_check(catalog['trains'][release['catalog_train']][chart], chart_release)
        return chart_release

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

        # TODO: Let's please use branch as well to keep an accurate track of which app belongs to which catalog branch
        catalog_items = {
            f'{c["id"]}_{train}_{item}': c['trains'][train][item]
            for c in await self.middleware.call('catalog.query', [], {'extra': {'item_details': True}})
            for train in c['trains'] for item in c['trains'][train]
        }
        for application in await self.middleware.call('chart.release.query', chart_releases_filters):
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
        available_versions = [parse_version(v) for v in catalog_item['versions']]
        if not available_versions:
            return

        available_versions.sort(reverse=True)
        if available_versions[0] > parse_version(application['chart_metadata']['version']):
            await self.middleware.call('alert.oneshot_create', 'ChartReleaseUpdate', application)
        else:
            await self.middleware.call('alert.oneshot_delete', 'ChartReleaseUpdate', f'"{application["id"]}"')

    @accepts(Str('release_name'))
    @job(lock=lambda args: f'pull_container_images{args[0]}')
    async def pull_container_images(self, job, release_name):
        images = await self.middleware.call('chart.release.retrieve_container_images', release_name)
        bulk_job = await self.middleware.call(
            'core.bulk', 'container.image.pull', [
                [{'from_image': f'{image["registry"]}/{image["image"]}', 'tag': image['tag']}]
                for image in images.values() if image['update_available']
            ]
        )
        await bulk_job.wait()
        return bulk_job.result
