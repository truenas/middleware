from __future__ import annotations

import middlewared.sqlalchemy as sa
from middlewared.api.current import CatalogEntry, CatalogUpdate
from middlewared.service import ConfigServicePart, ValidationErrors
from middlewared.utils import ProductType

from .utils import OFFICIAL_ENTERPRISE_TRAIN, OFFICIAL_LABEL


class CatalogModel(sa.Model):
    __tablename__ = 'services_catalog'

    label = sa.Column(sa.String(255), nullable=False, unique=True, primary_key=True)
    preferred_trains = sa.Column(sa.JSON(list))


class CatalogConfigPart(ConfigServicePart[CatalogEntry]):
    _datastore = 'services.catalog'
    _datastore_extend = 'catalog.extend'
    _datastore_extend_context = 'catalog.extend_context'
    _entry = CatalogEntry

    async def do_update(self, data: CatalogUpdate) -> CatalogEntry:
        verrors = ValidationErrors()
        if not data.preferred_trains:
            verrors.add(
                'catalog_update.preferred_trains',
                'At least 1 preferred train must be specified.'
            )
        if (
            await self.middleware.call('system.product_type') == ProductType.ENTERPRISE and
            OFFICIAL_ENTERPRISE_TRAIN not in data.preferred_trains
        ):
            verrors.add(
                'catalog_update.preferred_trains',
                f'Enterprise systems must at least have {OFFICIAL_ENTERPRISE_TRAIN!r} train enabled'
            )

        verrors.check()

        await self.middleware.call(
            'datastore.update',
            self._datastore,
            OFFICIAL_LABEL,
            data.model_dump(),
        )

        return await self.config()
