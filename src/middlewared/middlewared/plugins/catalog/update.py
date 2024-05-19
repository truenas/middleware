import errno
import os
import shutil

import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Bool, Dict, List, Patch, Str
from middlewared.service import CallError, CRUDService, job, private, ValidationErrors
from middlewared.validators import Match


OFFICIAL_ENTERPRISE_TRAIN = 'enterprise'


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
        datastore_primary_key = 'label'
        datastore_primary_key_type = 'string'
        cli_namespace = 'app.catalog'
        namespace = 'catalog'

    ENTRY = Patch(
        'catalog_create', 'catalog_entry',
        ('add', Bool('builtin')),
        ('add', Str('id')),
        ('rm', {'name': 'force'}),
    )

    @private
    def extend(self, data):
        data['id'] = data['label']
        return data

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
            Bool('force', default=False),
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

        if os.path.exists(catalog['location']):
            shutil.rmtree(catalog['location'], ignore_errors=True)

        return ret

