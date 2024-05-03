import contextlib
import errno
import os
import shutil

import middlewared.sqlalchemy as sa

from middlewared.schema import Any, Bool, Dict, Float, List, Patch, Str, ValidationErrors
from middlewared.service import accepts, CallError, CRUDService, job, private
from middlewared.utils import filter_list, MIDDLEWARE_RUN_DIR
from middlewared.validators import Match

from .utils import convert_repository_to_path, get_cache_key

OFFICIAL_ENTERPRISE_TRAIN = 'enterprise'
OFFICIAL_LABEL = 'TRUENAS'
TMP_IX_APPS_DIR = os.path.join(MIDDLEWARE_RUN_DIR, 'ix-applications')


class CatalogModel(sa.Model):
    __tablename__ = 'services_catalog'

    label = sa.Column(sa.String(255), nullable=False, unique=True, primary_key=True)
    repository = sa.Column(sa.Text(), nullable=False)
    branch = sa.Column(sa.String(255), nullable=False)
    builtin = sa.Column(sa.Boolean(), nullable=False, default=False)
    preferred_trains = sa.Column(sa.JSON(list))


class CatalogService(CRUDService):

    class Config:
        datastore = 'services.catalog'
        datastore_extend = 'catalog.catalog_extend'
        datastore_extend_context = 'catalog.catalog_extend_context'
        datastore_primary_key = 'label'
        datastore_primary_key_type = 'string'
        cli_namespace = 'app.catalog'
        role_prefix = 'CATALOG'

    ENTRY = Dict(
        'catalog_entry',
        Str(
            'label', required=True, validators=[Match(
                r'^\w+[\w.-]*$',
                explanation='Label must start with an alphanumeric character and can include dots and dashes.'
            )],
            max_length=60,
        ),
        Str('repository', required=True, empty=False),
        Str('branch', required=True, empty=False),
        Str('location', required=True),
        Str('id', required=True),
        List('preferred_trains'),
        Dict('trains', additional_attrs=True),
        Bool('healthy'),
        Bool('error'),
        Bool('builtin'),
        Bool('cached'),
        Dict(
            'caching_progress',
            Str('description', null=True),
            Any('extra', null=True),
            Float('percent', null=True),
            null=True,
        ),
        Dict('caching_job', null=True, additional_attrs=True),
    )

    @private
    async def catalog_extend_context(self, rows, extra):
        if await self.dataset_mounted():
            catalogs_dir = (await self.middleware.call('kubernetes.config'))['dataset']
        else:
            # FIXME: TMP_IX_APPS_DIR is in tmpfs (RAM)....a large catalog
            # will eat a large amount of RAM....
            catalogs_dir = os.path.join(TMP_IX_APPS_DIR, 'catalogs')

        context = {
            'catalogs_dir': catalogs_dir,
            'extra': extra or {},
            'catalogs_context': {},
        }
        if extra.get('item_details'):
            sync_jobs = await self.middleware.call(
                'core.get_jobs', [['method', '=', 'catalog.sync'], ['state', '=', 'RUNNING']]
            )
            for row in rows:
                label = row['label']
                catalog_info = {
                    'cached': label == OFFICIAL_LABEL or await self.middleware.call('catalog.cached', label),
                    'normalized_progress': None,
                    'trains': extra.get('trains', []),
                    'retrieve_all_trains': extra.get('retrieve_all_trains', True),
                }
                if not catalog_info['cached']:
                    sync_job = filter_list(sync_jobs, [['arguments', '=', [row['label']]]])
                    if sync_job:
                        # We will almost certainly always have this except for the case when middleware starts
                        # it is guaranteed that we will eventually have this anyways as catalog.sync_all is called
                        # periodically. So let's not trigger a new redundant job for this
                        sync_job = sync_job[0]
                    else:
                        sync_job = None

                    catalog_info['normalized_progress'] = {
                        'sync_job': sync_job,
                        'sync_progress': sync_job['progress'] if sync_job else None,
                    }
                context['catalogs_context'][label] = catalog_info

        return context

    @private
    async def normalize_data_from_context(self, label, catalog_context):
        normalized = {
            'trains': {},
            'cached': catalog_context['cached'],
            'healthy': False,
            'error': True,
            'caching_progress': None,
            'caching_job': None,
        }
        with contextlib.suppress(Exception):
            # We don't care why it failed, we don't want catalog.query to fail
            # Failure will be caught by other automatic invocations automatically
            trains = await self.middleware.call('catalog.items', label, {
                'cache': True,
                'cache_only': await self.official_catalog_label() != label,
                'retrieve_all_trains': catalog_context['retrieve_all_trains'],
                'trains': catalog_context['trains'],
            })
            normalized.update({
                'trains': trains,
                'healthy': all(
                    app['healthy'] for train in trains for app in trains[train].values()
                ),
                'cached': catalog_context['cached'],
                'error': False,
                'caching_progress': None,
                'caching_job': None,
            })
        return normalized

    @private
    async def catalog_extend(self, catalog, context):
        catalog.update({
            'location': os.path.join(
                context['catalogs_dir'], convert_repository_to_path(catalog['repository'], catalog['branch'])
            ),
            'id': catalog['label'],
        })
        extra = context['extra']
        if extra.get('item_details'):
            catalog_context = context['catalogs_context'][catalog['label']]
            catalog.update(await self.normalize_data_from_context(catalog['id'], catalog_context))
            if catalog['cached']:
                return catalog
            else:
                catalog.update(catalog_context['normalized_progress'])
        return catalog

    @private
    async def common_validation(self, catalog, schema, data):
        found_trains = set(catalog['trains'])
        diff = set(data['preferred_trains']) - found_trains
        verrors = ValidationErrors()
        if diff:
            verrors.add(
                f'{schema}.preferred_trains',
                f'{", ".join(diff)} trains were not found in catalog.'
            )
        if not data['preferred_trains']:
            verrors.add(
                f'{schema}.preferred_trains',
                'At least 1 preferred train must be specified for a catalog.'
            )
        if (
            await self.middleware.call('system.product_type') == 'SCALE_ENTERPRISE' and
            OFFICIAL_ENTERPRISE_TRAIN not in data['preferred_trains']
        ):
            verrors.add(
                f'{schema}.preferred_trains',
                f'Enterprise systems must at least have {OFFICIAL_ENTERPRISE_TRAIN!r} train enabled'
            )

        verrors.check()

    @private
    async def dataset_mounted(self):
        if k8s_dataset := (await self.middleware.call('kubernetes.config'))['dataset']:
            return bool(await self.middleware.call(
                'filesystem.mount_info', [
                    ['mount_source', '=', os.path.join(k8s_dataset, 'catalogs')], ['fs_type', '=', 'zfs'],
                ],
            ))

        return False

    @private
    async def cannot_be_added(self):
        if not await self.middleware.call('kubernetes.pool_configured'):
            return 'Catalogs cannot be added until apps pool is configured'
        elif (await self.middleware.call('kubernetes.config'))['passthrough_mode']:
            return 'Catalogs cannot be added when passthrough mode is enabled for apps'

        return False

    @accepts(
        Patch(
            'catalog_entry',
            'catalog_create',
            ('add', Bool('force', default=False)),
            ('rm', {'name': 'id'}),
            ('rm', {'name': 'trains'}),
            ('rm', {'name': 'healthy'}),
            ('rm', {'name': 'error'}),
            ('rm', {'name': 'builtin'}),
            ('rm', {'name': 'location'}),
            ('rm', {'name': 'cached'}),
            ('rm', {'name': 'caching_progress'}),
            ('rm', {'name': 'caching_job'}),
        ),
    )
    @job(lock=lambda args: f'catalog_create_{args[0]["label"]}')
    async def do_create(self, job, data):
        """
        `catalog_create.preferred_trains` specifies trains which will be displayed in the UI directly for a user.
        """
        verrors = ValidationErrors()
        # We normalize the label
        data['label'] = data['label'].upper()

        if error := await self.cannot_be_added():
            verrors.add('catalog_create.label', error)

        if await self.query([['id', '=', data['label']]]):
            verrors.add('catalog_create.label', 'A catalog with specified label already exists', errno=errno.EEXIST)

        if await self.query([['repository', '=', data['repository']], ['branch', '=', data['branch']]]):
            for k in ('repository', 'branch'):
                verrors.add(
                    f'catalog_create.{k}', 'A catalog with same repository/branch already exists', errno=errno.EEXIST
                )

        if not await self.can_system_add_catalog():
            verrors.add(
                'catalog_create.label',
                'Enterprise systems are not allowed to add catalog(s)'
            )

        verrors.check()

        if not data['preferred_trains']:
            data['preferred_trains'] = ['stable']

        if not data.pop('force'):
            job.set_progress(40, f'Validating {data["label"]!r} catalog')
            # We will validate the catalog now to ensure it's valid wrt contents / format
            k8s_dataset = (await self.middleware.call('kubernetes.config'))['dataset']
            path = os.path.join(
                '/mnt', k8s_dataset, 'catalogs/validate_catalogs',
                convert_repository_to_path(data['repository'], data['branch'])
            )
            await self.middleware.run_in_thread(shutil.rmtree, path, ignore_errors=True)
            try:
                await self.middleware.call('catalog.update_git_repository', {**data, 'location': path})
                await self.middleware.call('catalog.validate_catalog_from_path', path)
                await self.common_validation(
                    {'trains': await self.middleware.call('catalog.retrieve_train_names', path)}, 'catalog_create', data
                )
            except ValidationErrors as ve:
                verrors.extend(ve)
            except CallError as e:
                verrors.add('catalog_create.label', f'Failed to validate catalog: {e}')
            finally:
                await self.middleware.run_in_thread(shutil.rmtree, path, ignore_errors=True)
        else:
            job.set_progress(50, 'Skipping validation of catalog')

        verrors.check()

        job.set_progress(60, 'Completed Validation')

        await self.middleware.call('datastore.insert', self._config.datastore, data)
        job.set_progress(70, f'Successfully added {data["label"]!r} catalog')

        job.set_progress(80, f'Syncing {data["label"]} catalog')
        sync_job = await self.middleware.call('catalog.sync', data['label'])
        await sync_job.wait()
        if sync_job.error:
            raise CallError(f'Catalog was added successfully but failed to sync: {sync_job.error}')

        job.set_progress(100, f'Successfully synced {data["label"]!r} catalog')

        return await self.get_instance(data['label'])

    @accepts(
        Str('id'),
        Dict(
            'catalog_update',
            List('preferred_trains'),
            update=True
        )
    )
    async def do_update(self, id_, data):
        catalog = await self.query([['id', '=', id_]], {'extra': {'item_details': True}, 'get': True})
        await self.common_validation(catalog, 'catalog_update', data)

        await self.middleware.call('datastore.update', self._config.datastore, id_, data)

        return await self.get_instance(id_)

    def do_delete(self, id_):
        catalog = self.middleware.call_sync('catalog.get_instance', id_)
        if catalog['builtin']:
            raise CallError('Builtin catalogs cannot be deleted')

        ret = self.middleware.call_sync('datastore.delete', self._config.datastore, id_)

        if os.path.exists(catalog['location']):
            shutil.rmtree(catalog['location'], ignore_errors=True)

        # Let's delete any unhealthy alert if we had one
        self.middleware.call_sync('alert.oneshot_delete', 'CatalogNotHealthy', id_)
        self.middleware.call_sync('alert.oneshot_delete', 'CatalogSyncFailed', id_)

        # Remove cached content of the catalog in question so that if a catalog is created again
        # with same label but different repo/branch, we don't reuse old cache
        self.middleware.call_sync('cache.pop', get_cache_key(id_))

        return ret

    @private
    async def can_system_add_catalog(self):
        if await self.middleware.call('system.product_type') != 'SCALE_ENTERPRISE':
            return True

        # If system is not HA capable and is not R series, we can add catalog
        if not await self.middleware.call('system.is_ha_capable') and not (
            await self.middleware.call('failover.hardware')
        ).startswith('TRUENAS-R'):
            return True

        return False

    @private
    async def official_catalog_label(self):
        return OFFICIAL_LABEL

    @private
    async def official_enterprise_train(self):
        return OFFICIAL_ENTERPRISE_TRAIN

    @private
    async def update_train_for_enterprise(self):
        catalog = await self.middleware.call('catalog.get_instance', OFFICIAL_LABEL)
        if await self.middleware.call('system.product_type') == 'SCALE_ENTERPRISE':
            can_system_add_catalog = await self.can_system_add_catalog()
            preferred_trains = []
            if OFFICIAL_ENTERPRISE_TRAIN not in catalog['preferred_trains'] and can_system_add_catalog:
                preferred_trains = catalog['preferred_trains'] + [OFFICIAL_ENTERPRISE_TRAIN]
            elif not can_system_add_catalog:
                preferred_trains = [OFFICIAL_ENTERPRISE_TRAIN]

            if preferred_trains:
                await self.middleware.call(
                    'datastore.update', self._config.datastore, OFFICIAL_LABEL, {
                        'preferred_trains': preferred_trains,
                    },
                )


async def enterprise_train_update(middleware, prev_product_type, *args, **kwargs):
    await middleware.call('catalog.update_train_for_enterprise')


async def setup(middleware):
    middleware.register_hook('system.post_license_update', enterprise_train_update)
