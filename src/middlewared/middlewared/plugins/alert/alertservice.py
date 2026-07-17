from __future__ import annotations

import copy
import typing
import uuid

from pydantic_core import ValidationError

from middlewared.alert.base import Alert
from middlewared.alert.base import (
    AlertService as _AlertService,
)
from middlewared.api import api_method
from middlewared.api.current import (
    AlertServiceCreate,
    AlertServiceCreateArgs,
    AlertServiceCreateResult,
    AlertServiceDeleteArgs,
    AlertServiceDeleteResult,
    AlertServiceEntry,
    AlertServiceTestArgs,
    AlertServiceTestResult,
    AlertServiceUpdateArgs,
    AlertServiceUpdateResult,
)
from middlewared.service import GenericCRUDService, private
from middlewared.utils.time_utils import utc_now

from .alertservice_crud import AlertServiceServicePart, TestAlert

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ("AlertServiceService",)


class AlertServiceService(GenericCRUDService[AlertServiceEntry]):
    class Config:
        datastore = "system.alertservice"
        datastore_order_by = ["name"]
        cli_namespace = "system.alert.service"
        entry = AlertServiceEntry
        role_prefix = "ALERT"
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = AlertServiceServicePart(self.context)

    @api_method(AlertServiceCreateArgs, AlertServiceCreateResult, check_annotations=True)
    async def do_create(self, data: AlertServiceCreate) -> AlertServiceEntry:
        """
        Create an Alert Service of specified ``type``.

        If ``enabled``, it sends alerts to the configured ``type`` of Alert Service.
        """
        return await self._svc_part.do_create(data)

    @api_method(AlertServiceUpdateArgs, AlertServiceUpdateResult, check_annotations=True)
    async def do_update(self, id_: int, data: AlertServiceCreate) -> AlertServiceEntry:
        """
        Update Alert Service of ``id``.
        """
        return await self._svc_part.do_update(id_, data)

    @api_method(AlertServiceDeleteArgs, AlertServiceDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> bool:
        """
        Delete Alert Service of ``id``.
        """
        return await self._svc_part.do_delete(id_)

    @api_method(AlertServiceTestArgs, AlertServiceTestResult, roles=["ALERT_WRITE"], check_annotations=True)
    async def test(self, data: AlertServiceCreate) -> bool:
        """
        Send a test alert using ``type`` of Alert Service.
        """
        self._svc_part._validate(data, "alert_service_test")

        factory = _AlertService.by_name[data.attributes.type]
        alert_service = factory(self.middleware, data.attributes.model_dump(expose_secrets=True))

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
    async def initialize(self) -> None:
        for alertservice in await self.middleware.call("datastore.query", "system.alertservice"):
            if alertservice["type"] not in _AlertService.by_name:
                self.logger.debug("Removing obsolete alert service %r (%r)", alertservice["name"], alertservice["type"])
                await self.middleware.call("datastore.delete", "system.alertservice", alertservice["id"])
                continue

            try:
                AlertServiceEntry.model_validate(self._svc_part.extend(copy.deepcopy(alertservice), {}))
            except ValidationError as e:
                attributes = copy.copy(alertservice["attributes"])
                for error in e.errors():
                    if (
                        error["type"] == "extra_forbidden"
                        and len(error["loc"]) == 3
                        and error["loc"][0] == "attributes"
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
                    await self.middleware.call(
                        "datastore.update",
                        "system.alertservice",
                        alertservice["id"],
                        {
                            "attributes": attributes,
                        },
                    )
