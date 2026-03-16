from __future__ import annotations

import copy
import typing
from typing import Any
import uuid

from pydantic_core import ValidationError

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
    AlertService as _AlertService,
)
from middlewared.api import api_method
from middlewared.api.current import (
    AlertServiceCreate,
    AlertServiceCreateArgs, AlertServiceCreateResult,
    AlertServiceDeleteArgs, AlertServiceDeleteResult,
    AlertServiceEntry,
    AlertServiceTestArgs, AlertServiceTestResult,
    AlertServiceUpdateArgs, AlertServiceUpdateResult,
)
from middlewared.service import CRUDServicePart, GenericCRUDService, ValidationErrors, private
import middlewared.sqlalchemy as sa
import middlewared.alert.service  # noqa: F401
from middlewared.utils.time_utils import utc_now

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


class TestAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.CRITICAL,
        title="Test alert",
        exclude_from_list=True,
    )


class AlertServiceModel(sa.Model):
    __tablename__ = 'system_alertservice'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(120))
    type = sa.Column(sa.String(20))
    attributes = sa.Column(sa.JSON(dict))
    enabled = sa.Column(sa.Boolean())
    level = sa.Column(sa.String(20))


class AlertServiceServicePart(CRUDServicePart[AlertServiceEntry]):
    _datastore = 'system.alertservice'
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


__all__ = ('AlertServiceService',)


class AlertServiceService(GenericCRUDService[AlertServiceEntry]):

    class Config:
        datastore = 'system.alertservice'
        datastore_order_by = ['name']
        cli_namespace = 'system.alert.service'
        entry = AlertServiceEntry
        role_prefix = 'ALERT'
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = AlertServiceServicePart(self.context)

    @api_method(AlertServiceCreateArgs, AlertServiceCreateResult, check_annotations=True)
    async def do_create(self, data: AlertServiceCreate) -> AlertServiceEntry:
        """
        Create an Alert Service of specified `type`.

        If `enabled`, it sends alerts to the configured `type` of Alert Service.
        """
        return await self._svc_part.do_create(data)

    @api_method(AlertServiceUpdateArgs, AlertServiceUpdateResult, check_annotations=True)
    async def do_update(self, id_: int, data: AlertServiceCreate) -> AlertServiceEntry:
        """
        Update Alert Service of `id`.
        """
        return await self._svc_part.do_update(id_, data)

    @api_method(AlertServiceDeleteArgs, AlertServiceDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> bool:
        """
        Delete Alert Service of `id`.
        """
        return await self._svc_part.do_delete(id_)

    @api_method(AlertServiceTestArgs, AlertServiceTestResult, roles=['ALERT_WRITE'], check_annotations=True)
    async def test(self, data: AlertServiceCreate) -> bool:
        """
        Send a test alert using `type` of Alert Service.
        """
        self._svc_part._validate(data, "alert_service_test")

        factory = _AlertService.by_name[data.attributes.type]
        alert_service = factory(self.middleware, data.attributes.model_dump(context={"expose_secrets": True}))

        master_node = "A"
        if await self.middleware.call("failover.licensed"):
            master_node = await self.middleware.call("failover.node")

        test_alert = Alert(
            TestAlert(),
            node=master_node,
            datetime=utc_now(),
            last_occurrence=utc_now(),
            _uuid=str(uuid.uuid4()),
        )

        try:
            await alert_service.send([test_alert], [], [test_alert])
        except Exception:
            self.logger.error("Error in alert service %r", data.attributes.type, exc_info=True)
            return False

        return True

    @private
    async def initialize(self):
        for alertservice in await self.middleware.call("datastore.query", "system.alertservice"):
            if alertservice["type"] not in _AlertService.by_name:
                self.logger.debug("Removing obsolete alert service %r (%r)", alertservice["name"], alertservice["type"])
                await self.middleware.call("datastore.delete", "system.alertservice", alertservice["id"])
                continue

            try:
                AlertServiceEntry.model_validate(
                    self._svc_part.extend(copy.deepcopy(alertservice), {})
                )
            except ValidationError as e:
                attributes = copy.copy(alertservice["attributes"])
                for error in e.errors():
                    if (
                        error["type"] == "extra_forbidden" and
                        len(error["loc"]) == 3 and
                        error["loc"][0] == "attributes"
                    ):
                        attribute = error["loc"][2]
                        attributes.pop(attribute, None)
                        self.logger.debug(
                            "Removing obsolete attribute %r for alert service %r (%r)",
                            attribute,
                            alertservice["name"],
                            alertservice["type"],
                        )
                    else:
                        self.logger.debug(
                            "Unknown validaton error for alert service %r (%r): %r. Removing it completely",
                            alertservice["name"],
                            alertservice["type"],
                            error,
                        )
                        await self.middleware.call("datastore.delete", "system.alertservice", alertservice["id"])
                        break
                else:
                    await self.middleware.call("datastore.update", "system.alertservice", alertservice["id"], {
                        "attributes": attributes,
                    })
