from __future__ import annotations

import typing

import middlewared.sqlalchemy as sa
from middlewared.api.current import CatalogEntry, CatalogUpdate
from middlewared.service import ConfigServicePart, ValidationErrors
from middlewared.utils import ProductType

from .utils import OFFICIAL_ENTERPRISE_TRAIN, OFFICIAL_LABEL

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


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

    async def update_train_for_enterprise(self) -> None:
        catalog = await self.config()
        if await self.middleware.call('system.product_type') == ProductType.ENTERPRISE:
            preferred_trains = []
            # Logic coming from here
            # https://github.com/truenas/middleware/blob/e7f2b29b6ff8fadcc9fdd8d7f104cbbf5172fc5a/src/middlewared
            # /middlewared/plugins/catalogs_linux/update.py#L341
            can_have_multiple_trains = not await self.middleware.call('system.is_ha_capable') and not (
                await self.middleware.call('failover.hardware')
            ).startswith('TRUENAS-R')
            if OFFICIAL_ENTERPRISE_TRAIN not in catalog.preferred_trains and can_have_multiple_trains:
                preferred_trains = catalog.preferred_trains + [OFFICIAL_ENTERPRISE_TRAIN]
            elif not can_have_multiple_trains:
                preferred_trains = [OFFICIAL_ENTERPRISE_TRAIN]

            if preferred_trains:
                await self.middleware.call(
                    'datastore.update', self._datastore, OFFICIAL_LABEL, {
                        'preferred_trains': preferred_trains,
                    },
                )


async def enterprise_train_update(middleware: Middleware, *args: typing.Any, **kwargs: typing.Any) -> None:
    await middleware.call('catalog.update_train_for_enterprise')


async def setup(middleware: Middleware) -> None:
    middleware.register_hook('system.post_license_update', enterprise_train_update)
