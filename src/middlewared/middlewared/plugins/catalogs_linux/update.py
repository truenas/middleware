import errno
import os
import shutil

import middlewared.sqlalchemy as sa

from middlewared.schema import Any, Bool, Dict, Float, List, Patch, Str, ValidationErrors
from middlewared.service import accepts, CallError, CRUDService, job, private
from middlewared.utils import filter_list
from middlewared.validators import Match

from .utils import convert_repository_to_path, get_cache_key

OFFICIAL_ENTERPRISE_TRAIN = 'enterprise'
OFFICIAL_LABEL = 'OFFICIAL'
TMP_IX_APPS_DIR = '/tmp/ix-applications'


class CatalogModel(sa.Model):
    __tablename__ = 'services_catalog'

    label = sa.Column(sa.String(255), nullable=False, unique=True, primary_key=True)
    repository = sa.Column(sa.Text(), nullable=False)
    branch = sa.Column(sa.String(255), nullable=False)
    builtin = sa.Column(sa.Boolean(), nullable=False, default=False)
    preferred_trains = sa.Column(sa.JSON(type=list))


class CatalogService(CRUDService):

    class Config:
        datastore = 'services.catalog'
        datastore_extend = 'catalog.catalog_extend'
        datastore_extend_context = 'catalog.catalog_extend_context'
        datastore_primary_key = 'label'
        datastore_primary_key_type = 'string'
        cli_namespace = 'app.catalog'

    ENTRY = Dict(
        'catalog_entry',
        Str('label', required=True, validators=[Match(r'^\w+[\w.-]*$')], max_length=60),
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
        k8s_dataset = (await self.middleware.call('kubernetes.config'))['dataset']
        catalogs_ds = await self.middleware.call(
            'zfs.dataset.query', [['id', '=', os.path.join(k8s_dataset, 'catalogs')]], {
                'extra': {'properties': ['encryption', 'keystatus', 'mountpoint', 'mounted']}
            }
        ) if k8s_dataset else []
        if k8s_dataset and catalogs_ds and (
            catalogs_ds[0]['properties']['mounted']['parsed'] and (
                (catalogs_ds[0]['encrypted'] and catalogs_ds[0]['key_loaded']) or not catalogs_ds[0]['encrypted']
            )
        ):
            catalogs_dir = catalogs_ds[0]['properties']['mountpoint']['parsed']
        else:
            catalogs_dir = os.path.join(TMP_IX_APPS_DIR, 'catalogs')

        context = {
            'catalogs_dir': catalogs_dir,
            'extra': extra or {},
            'catalogs_context': {},
        }
        if extra.get('item_details'):
            item_sync_params = await self.middleware.call('catalog.sync_items_params')
            item_jobs = await self.middleware.call(
                'core.get_jobs', [['method', '=', 'catalog.items'], ['state', '=', 'RUNNING']]
            )
            for row in rows:
                label = row['label']
                catalog_info = {
                    'item_job': await self.middleware.call('catalog.items', label, {
                        'cache': True,
                        'cache_only': await self.official_catalog_label() != row['label'],
                        'retrieve_all_trains': extra.get('retrieve_all_trains', True),
                        'trains': extra.get('trains', []),
                    }),
                    'cached': label == OFFICIAL_LABEL or await self.middleware.call('catalog.cached', label),
                    'normalized_progress': None,
                }
                if not catalog_info['cached']:
                    caching_job = filter_list(item_jobs, [['arguments', '=', [row['label'], item_sync_params]]])
                    if caching_job:
                        # We will almost certainly always have this except for the case when middleware starts
                        # it is guaranteed that we will eventually have this anyways as catalog.sync_all is called
                        # periodically. So let's not trigger a new redundant job for this
                        caching_job = caching_job[0]
                    else:
                        caching_job = None

                    catalog_info['normalized_progress'] = {
                        'caching_job': caching_job,
                        'caching_progress': caching_job['progress'] if caching_job else None,
                    }
                context['catalogs_context'][label] = catalog_info

        return context

    @private
    async def normalize_data_from_item_job(self, label, catalog_context):
        normalized = {
            'trains': {},
            'cached': catalog_context['cached'],
            'healthy': False,
            'error': True,
            'caching_progress': None,
            'caching_job': None,
        }
        item_job = catalog_context['item_job']
        await item_job.wait()
        if not item_job.error:
            normalized.update({
                'trains': item_job.result,
                'healthy': all(
                    app['healthy'] for train in item_job.result for app in item_job.result[train].values()
                ),
                'cached': label == OFFICIAL_LABEL or await self.middleware.call('catalog.cached', label),
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
            catalog.update(await self.normalize_data_from_item_job(catalog['id'], catalog_context))
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

        verrors.check()

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

        if await self.query([['id', '=', data['label']]]):
            verrors.add('catalog_create.label', 'A catalog with specified label already exists', errno=errno.EEXIST)

        if await self.query([['repository', '=', data['repository']], ['branch', '=', data['branch']]]):
            for k in ('repository', 'branch'):
                verrors.add(
                    f'catalog_create.{k}', 'A catalog with same repository/branch already exists', errno=errno.EEXIST
                )

        verrors.check()

        if not data['preferred_trains']:
            data['preferred_trains'] = ['stable']

        if not data.pop('force'):
            job.set_progress(40, f'Validating {data["label"]!r} catalog')
            # We will validate the catalog now to ensure it's valid wrt contents / format
            path = os.path.join(
                TMP_IX_APPS_DIR, 'validate_catalogs', convert_repository_to_path(data['repository'], data['branch'])
            )
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
    async def do_update(self, id, data):
        catalog = await self.query([['id', '=', id]], {'extra': {'item_details': True}, 'get': True})
        await self.common_validation(catalog, 'catalog_update', data)

        await self.middleware.call('datastore.update', self._config.datastore, id, data)

        return await self.get_instance(id)

    def do_delete(self, id):
        catalog = self.middleware.call_sync('catalog.get_instance', id)
        if catalog['builtin']:
            raise CallError('Builtin catalogs cannot be deleted')

        ret = self.middleware.call_sync('datastore.delete', self._config.datastore, id)

        if os.path.exists(catalog['location']):
            shutil.rmtree(catalog['location'], ignore_errors=True)

        # Let's delete any unhealthy alert if we had one
        self.middleware.call_sync('alert.oneshot_delete', 'CatalogNotHealthy', id)
        self.middleware.call_sync('alert.oneshot_delete', 'CatalogSyncFailed', id)

        # Remove cached content of the catalog in question so that if a catalog is created again
        # with same label but different repo/branch, we don't reuse old cache
        self.middleware.call_sync('cache.pop', get_cache_key(id))

        return ret

    @private
    async def official_catalog_label(self):
        return OFFICIAL_LABEL


async def enterprise_train_update(middleware, prev_product_type, *args, **kwargs):
    if prev_product_type != 'SCALE_ENTERPRISE' and await middleware.call('system.product_type') == 'SCALE_ENTERPRISE':
        await middleware.call('catalog.update', OFFICIAL_LABEL, {'preferred_trains': [OFFICIAL_ENTERPRISE_TRAIN]})


async def setup(middleware):
    middleware.register_hook('system.post_license_update', enterprise_train_update)
