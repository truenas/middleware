from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    SupportNewTicket,
    TrueNASAcceptEulaArgs,
    TrueNASAcceptEulaResult,
    TrueNASGetChassisHardwareArgs,
    TrueNASGetChassisHardwareResult,
    TrueNASGetEulaArgs,
    TrueNASGetEulaResult,
    TrueNASIsEulaAcceptedArgs,
    TrueNASIsEulaAcceptedResult,
    TrueNASIsIxHardwareArgs,
    TrueNASIsIxHardwareResult,
    TrueNASIsProductionArgs,
    TrueNASIsProductionResult,
    TrueNASManagedByTruecommandArgs,
    TrueNASManagedByTruecommandResult,
    TrueNASSetProductionArgs,
    TrueNASSetProductionResult,
)
from middlewared.job import Job
from middlewared.service import Service, job, private

from .license import TrueNASLicenseService
from .tn import (
    accept_eula as tn_accept_eula,
)
from .tn import (
    get_chassis_hardware as tn_get_chassis_hardware,
)
from .tn import (
    get_eula as tn_get_eula,
)
from .tn import (
    is_eula_accepted as tn_is_eula_accepted,
)
from .tn import (
    is_ix_hardware as tn_is_ix_hardware,
)
from .tn import (
    is_production as tn_is_production,
)
from .tn import (
    managed_by_truecommand as tn_managed_by_truecommand,
)
from .tn import (
    set_production as tn_set_production,
)
from .tn import (
    unaccept_eula as tn_unaccept_eula,
)

if TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ("TrueNASService",)


class TrueNASService(Service):

    class Config:
        cli_namespace = "system.truenas"

    def __init__(self, middleware: Middleware):
        super().__init__(middleware)
        self.license = TrueNASLicenseService(middleware)

    @api_method(
        TrueNASManagedByTruecommandArgs, TrueNASManagedByTruecommandResult,
        authentication_required=False, check_annotations=True,
    )
    async def managed_by_truecommand(self) -> bool:
        """Returns whether TrueNAS is being managed by TrueCommand."""
        return await tn_managed_by_truecommand(self.context)

    @api_method(
        TrueNASGetChassisHardwareArgs, TrueNASGetChassisHardwareResult,
        cli_private=True, roles=["READONLY_ADMIN"], check_annotations=True,
    )
    def get_chassis_hardware(self) -> str:
        """Returns what type of hardware this is, detected from dmidecode."""
        return tn_get_chassis_hardware()

    @api_method(
        TrueNASIsIxHardwareArgs, TrueNASIsIxHardwareResult,
        roles=["READONLY_ADMIN"], check_annotations=True,
    )
    async def is_ix_hardware(self) -> bool:
        """Return a boolean value on whether this is hardware that iXsystems sells."""
        return await tn_is_ix_hardware(self.context)

    @api_method(
        TrueNASGetEulaArgs, TrueNASGetEulaResult,
        cli_private=True, roles=["READONLY_ADMIN"], check_annotations=True,
    )
    def get_eula(self) -> str | None:
        """Returns the TrueNAS End-User License Agreement (EULA)."""
        return tn_get_eula()

    @api_method(
        TrueNASIsEulaAcceptedArgs, TrueNASIsEulaAcceptedResult,
        cli_private=True, roles=["READONLY_ADMIN"], check_annotations=True,
    )
    def is_eula_accepted(self) -> bool:
        """Returns whether the EULA is accepted or not."""
        return tn_is_eula_accepted()

    @api_method(
        TrueNASAcceptEulaArgs, TrueNASAcceptEulaResult,
        roles=["FULL_ADMIN"], check_annotations=True,
    )
    def accept_eula(self) -> None:
        """Accept TrueNAS EULA."""
        tn_accept_eula()

    @api_method(
        TrueNASIsProductionArgs, TrueNASIsProductionResult,
        roles=["READONLY_ADMIN"], check_annotations=True,
    )
    async def is_production(self) -> bool:
        """Returns if system is marked as production."""
        return await tn_is_production(self.context)

    @api_method(
        TrueNASSetProductionArgs, TrueNASSetProductionResult,
        roles=["FULL_ADMIN"], check_annotations=True,
    )
    @job()
    async def set_production(self, job: Job, production: bool, attach_debug: bool = False) -> SupportNewTicket | None:
        """Sets system production state and optionally sends initial debug."""
        return await tn_set_production(self.context, job, production, attach_debug)

    @private
    def unaccept_eula(self) -> None:
        tn_unaccept_eula()
