import os

import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import (
    CatalogEntry, CatalogUpdateArgs, CatalogUpdateResult, CatalogTrainsArgs, CatalogTrainsResult,
)
from middlewared.plugins.docker.state_utils import catalog_ds_path, CATALOG_DATASET_NAME
from middlewared.service import ConfigService, private, ValidationErrors
from middlewared.utils import ProductType

from .utils import OFFICIAL_ENTERPRISE_TRAIN, OFFICIAL_LABEL, TMP_IX_APPS_CATALOGS


class CatalogModel(sa.Model):
    __tablename__ = 'services_catalog'

    label = sa.Column(sa.String(255), nullable=False, unique=True, primary_key=True)
    preferred_trains = sa.Column(sa.JSON(list))


class CatalogService(ConfigService):

    class Config:
        datastore = 'services.catalog'
        datastore_extend = 'catalog.extend'
        datastore_extend_context = 'catalog.extend_context'
        datastore_primary_key = 'label'
        datastore_primary_key_type = 'string'
        cli_namespace = 'app.catalog'
        namespace = 'catalog'
        role_prefix = 'CATALOG'
        entry = CatalogEntry

    @private
    def extend(self, data, context):
        data.update({
            'id': data['label'],
            'location': context['catalog_dir'],
        })
        return data

    @api_method(CatalogTrainsArgs, CatalogTrainsResult, roles=['CATALOG_READ'])
    async def trains(self):
        """
        Retrieve available trains.
        """
        return list(await self.middleware.call('catalog.apps', {'cache': True, 'cache_only': True}))
