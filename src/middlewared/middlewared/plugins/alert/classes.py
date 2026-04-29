from __future__ import annotations

import typing

from middlewared.alert.base import AlertClass
from middlewared.api import api_method
from middlewared.api.current import (
    AlertClassesEntry,
    AlertClassesUpdate,
    AlertClassesUpdateArgs,
    AlertClassesUpdateResult,
)
from middlewared.service import ConfigServicePart, GenericConfigService, ValidationErrors
import middlewared.sqlalchemy as sa

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


class AlertClassesModel(sa.Model):
    __tablename__ = "system_alertclasses"

    id = sa.Column(sa.Integer(), primary_key=True)
    classes = sa.Column(sa.JSON(dict))


class AlertClassesConfigServicePart(ConfigServicePart[AlertClassesEntry]):
    _datastore = "system.alertclasses"
    _entry = AlertClassesEntry

    async def do_update(self, data: AlertClassesUpdate) -> AlertClassesEntry:
        old = await self.config()

        new = old.model_dump()
        new.update(data.model_dump(exclude_unset=True))

        verrors = ValidationErrors()

        for k, v in new["classes"].items():
            if k not in AlertClass.by_name:
                verrors.add(f"alert_class_update.classes.{k}", "This alert class does not exist")
                continue

            if "proactive_support" in v and not AlertClass.by_name[k].config.proactive_support:
                verrors.add(
                    f"alert_class_update.classes.{k}.proactive_support",
                    "Proactive support is not supported by this alert class",
                )

        verrors.check()

        await self.middleware.call("datastore.update", self._datastore, old.id, new)

        return await self.config()


__all__ = ("AlertClassesService",)


class AlertClassesService(GenericConfigService[AlertClassesEntry]):

    class Config:
        datastore = "system.alertclasses"
        cli_namespace = "system.alert.class"
        entry = AlertClassesEntry
        role_prefix = "ALERT"
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = AlertClassesConfigServicePart(self.context)

    @api_method(AlertClassesUpdateArgs, AlertClassesUpdateResult, check_annotations=True)
    async def do_update(self, data: AlertClassesUpdate) -> AlertClassesEntry:
        """
        Update default Alert settings.
        """
        return await self._svc_part.do_update(data)
