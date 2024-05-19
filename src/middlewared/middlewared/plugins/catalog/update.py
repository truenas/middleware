import errno
import os

import middlewared.sqlalchemy as sa

from middlewared.plugins.docker.state_utils import catalog_ds_path
from middlewared.schema import accepts, Bool, Dict, List, Patch, Str
from middlewared.service import CallError, CRUDService, job, private, ValidationErrors
from middlewared.validators import Match

from .utils import convert_repository_to_path, OFFICIAL_ENTERPRISE_TRAIN, TMP_IX_APPS_CATALOGS


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
        datastore_extend = 'catalog.extend'
        datastore_extend_context = 'catalog.extend_context'
        datastore_primary_key = 'label'
        datastore_primary_key_type = 'string'
        cli_namespace = 'app.catalog'
        namespace = 'catalog'

    ENTRY = Patch(
        'catalog_create', 'catalog_entry',
        ('add', Bool('builtin')),
        ('add', Str('id')),
    )

    @private
    def extend(self, data, context):
        data.update({
            'id': data['label'],
            'location': os.path.join(
                context['catalog_dir'], convert_repository_to_path(data['repository'], data['branch'])
            )
        })
        return data

    @private
    async def extend_context(self, rows, extra):
        if await self.dataset_mounted():
            catalog_dir = catalog_ds_path((await self.middleware.call('docker.config'))['dataset'])
        else:
            # FIXME: This can eat lots of memory if it's a large catalog
            catalog_dir = TMP_IX_APPS_CATALOGS

        return {
            'catalog_dir': catalog_dir,
        }

    @private
    async def dataset_mounted(self):
        if docker_ds := (await self.middleware.call('docker.config'))['dataset']:
            return bool(await self.middleware.call(
                'filesystem.mount_info', [
                    ['mount_source', '=', os.path.join(docker_ds, 'catalogs')], ['fs_type', '=', 'zfs'],
                ],
            ))

        return False

    @private
    async def common_validation(self, schema, data):
        verrors = ValidationErrors()
        if not data['preferred_trains']:
            verrors.add(
                f'{schema}.preferred_trains',
                'At least 1 preferred train must be specified for a catalog_old.'
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

    @accepts(
        Dict(
            'catalog_create',
            List('preferred_trains'),
            Str(
                'label', required=True, validators=[Match(
                    r'^\w+[\w.-]*$',
                    explanation='Label must start with an alphanumeric character and can include dots and dashes.'
                )],
                max_length=60,
            ),
            Str('repository', required=True, empty=False),
            Str('branch', required=True, empty=False),
            register=True,
        )
    )
    @job(lock='catalog_create')
    async def do_create(self, job, data):
        """
        Create a new catalog entry.
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

        await self.common_validation('catalog_create', data)

        if not await self.can_system_add_catalog():
            verrors.add(
                'catalog_create.label',
                'Enterprise systems are not allowed to add catalog(s)'
            )

        verrors.check()

        job.set_progress(60, 'Completed catalog validation')

        if not data['preferred_trains']:
            data['preferred_trains'] = ['stable']

        await self.middleware.call('datastore.insert', self._config.datastore, data)

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
        """
        Update catalog entry of `id`.
        """
        await self.get_instance(id_)
        await self.common_validation('catalog_update', data)

        await self.middleware.call('datastore.update', self._config.datastore, id_, data)

        return await self.get_instance(id_)

    def do_delete(self, id_):
        """
        Delete catalog entry of `id`.
        """
        catalog = self.middleware.call_sync('catalog.get_instance', id_)
        if catalog['builtin']:
            raise CallError('Builtin catalogs cannot be deleted')

        ret = self.middleware.call_sync('datastore.delete', self._config.datastore, id_)

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
