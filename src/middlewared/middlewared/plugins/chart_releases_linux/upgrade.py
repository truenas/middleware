import errno
import os
import shutil
import tempfile
import yaml

from pkg_resources import parse_version

from middlewared.schema import Dict, Str
from middlewared.service import accepts, CallError, Service, ValidationErrors

from .schema import clean_values_for_upgrade
from .utils import get_namespace, run


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @accepts(
        Str('release_name'),
        Dict(
            'upgrade_options',
            Dict('values', additional_attrs=True),
            Str('item_version', required=True),
        )
    )
    async def upgrade(self, release_name, options):
        release = await self.middleware.call('chart.release.get_instance', release_name)
        catalog = await self.middleware.call(
            'catalog.query', [['id', '=', release['catalog']]], {'get': True, 'extra': {'item_details': True}},
        )

        new_version = options['item_version']
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

        # We have validated configuration now

        chart_path = os.path.join(release['path'], 'charts', new_version)
        await self.middleware.run_in_thread(lambda: shutil.rmtree(chart_path, ignore_errors=True))
        await self.middleware.run_in_thread(lambda: shutil.copytree(catalog_item['location'], chart_path))

        # If a snapshot of the volumes already exist with the same name in case of a failed upgrade, we will remove
        # it as we want the current point in time being reflected in the snapshot
        volumes_ds = os.path.join(release['dataset'], 'volumes/ix_volumes')
        snap_name = f'{volumes_ds}@{current_chart["version"]}'
        if await self.middleware.call('zfs.snapshot.query', [['id', '=', snap_name]]):
            await self.middleware.call('zfs.snapshot.delete', snap_name)

        await self.middleware.call(
            'zfs.snapshot.create', {'dataset': volumes_ds, 'name': current_chart['version']}
        )

        await self.middleware.call('chart.release.perform_actions', context)

        with tempfile.NamedTemporaryFile(mode='w+') as f:
            f.write(yaml.dump(config))
            f.flush()

            cp = await run(
                ['helm', 'upgrade', release_name, chart_path, '-n', get_namespace(release_name), '-f', f.name],
                check=False,
            )
            if cp.returncode:
                raise CallError(f'Failed to upgrade chart release to {new_version!r}: {cp.stderr.decode()}')

        return await self.middleware.call('chart.release.get_instance', release_name)
