from __future__ import annotations

import typing

import middlewared.sqlalchemy as sa
from middlewared.api.current import CatalogEntry
from middlewared.service import ConfigServicePart, ValidationErrors


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
