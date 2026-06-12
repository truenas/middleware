from __future__ import annotations

from middlewared.alert.base import AlertClass
from middlewared.api.current import AlertClassesEntry, AlertClassesUpdate
from middlewared.service import ConfigServicePart, ValidationErrors
import middlewared.sqlalchemy as sa


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
