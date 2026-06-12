from __future__ import annotations

from typing import Any

from middlewared.alert.base import (
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
)
from middlewared.alert.base import (
    AlertService as _AlertService,
)
import middlewared.alert.service  # noqa: F401
from middlewared.api.current import (
    AlertServiceCreate,
    AlertServiceEntry,
)
from middlewared.service import CRUDServicePart, ValidationErrors
import middlewared.sqlalchemy as sa


class TestAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.CRITICAL,
        title="Test alert",
        exclude_from_list=True,
    )


class AlertServiceModel(sa.Model):
    __tablename__ = "system_alertservice"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(120))
    type = sa.Column(sa.String(20))
    attributes = sa.Column(sa.JSON(dict))
    enabled = sa.Column(sa.Boolean())
    level = sa.Column(sa.String(20))


class AlertServiceServicePart(CRUDServicePart[AlertServiceEntry]):
    _datastore = "system.alertservice"
    _entry = AlertServiceEntry

    def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        data["attributes"]["type"] = data.pop("type")

        try:
            data["type__title"] = _AlertService.by_name[data["attributes"]["type"]].title
        except KeyError:
            data["type__title"] = "<Unknown>"

        return data

    def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        data["type"] = data["attributes"].pop("type")
        data.pop("type__title", None)
        return data

    async def do_create(self, data: AlertServiceCreate) -> AlertServiceEntry:
        self._validate(data, "alert_service_create")
        return await self._create(data.model_dump(context={"expose_secrets": True}))

    async def do_update(self, id_: int, data: AlertServiceCreate) -> AlertServiceEntry:
        old = await self.get_instance(id_)
        new_data = old.model_dump(context={"expose_secrets": True})
        new_data.update(data.model_dump(context={"expose_secrets": True}))
        self._validate_dict(new_data, "alert_service_update")
        return await self._update(id_, new_data)

    async def do_delete(self, id_: int) -> bool:
        await self.get_instance(id_)
        await self._delete(id_)
        return True

    def _validate(self, data: AlertServiceCreate, schema_name: str) -> None:
        verrors = ValidationErrors()

        levels = AlertLevel.__members__
        if data.level not in levels:
            verrors.add(f"{schema_name}.level", f"Level must be one of {list(levels)}")

        verrors.check()

    def _validate_dict(self, data: dict[str, Any], schema_name: str) -> None:
        verrors = ValidationErrors()

        levels = AlertLevel.__members__
        if data["level"] not in levels:
            verrors.add(f"{schema_name}.level", f"Level must be one of {list(levels)}")

        verrors.check()
