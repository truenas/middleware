import errno
import os

from ixhardware import TRUENAS_UNKNOWN, get_chassis_hardware

from middlewared.service import job, private, Service
from middlewared.api.current import (
    TrueNASSetProductionArgs, TrueNASSetProductionResult,
    TrueNASIsProductionArgs, TrueNASIsProductionResult,
    TrueNASAcceptEulaArgs, TrueNASAcceptEulaResult,
    TrueNASIsEulaAcceptedArgs, TrueNASIsEulaAcceptedResult,
    TrueNASGetEulaArgs, TrueNASGetEulaResult,
    TrueNASIsIxHardwareArgs, TrueNASIsIxHardwareResult,
    TrueNASGetChassisHardwareArgs, TrueNASGetChassisHardwareResult,
    TrueNASManagedByTruecommandArgs, TrueNASManagedByTruecommandResult, TruecommandStatus,
)
from middlewared.api import api_method

EULA_FILE = '/usr/local/share/truenas/eula.html'
EULA_PENDING_PATH = "/data/truenas-eula-pending"


class TrueNASService(Service):

    class Config:
        cli_namespace = 'system.truenas'

    @api_method(
        TrueNASManagedByTruecommandArgs,
        TrueNASManagedByTruecommandResult,
        authentication_required=False,
    )
    async def managed_by_truecommand(self):
        """
        Returns whether TrueNAS is being managed by TrueCommand
        """
        # NOTE: This endpoint doesn't require authentication because
        # it is used by UI on the login page
        return TruecommandStatus(
            (await self.middleware.call('truecommand.config'))['status']
        ) == TruecommandStatus.CONNECTED

    @api_method(
        TrueNASGetChassisHardwareArgs,
        TrueNASGetChassisHardwareResult,
        cli_private=True,
        roles=['READONLY_ADMIN'],
    )
    async def get_chassis_hardware(self):
        """
        Returns what type of hardware this is, detected from dmidecode.
        """
        return get_chassis_hardware()

    @api_method(TrueNASIsIxHardwareArgs, TrueNASIsIxHardwareResult, roles=['READONLY_ADMIN'])
    async def is_ix_hardware(self):
        """
        Return a boolean value on whether this is hardware that iXsystems sells.
        """
        return await self.get_chassis_hardware() != TRUENAS_UNKNOWN

    @api_method(TrueNASGetEulaArgs, TrueNASGetEulaResult, cli_private=True, roles=['READONLY_ADMIN'])
    def get_eula(self):
        """
        Returns the TrueNAS End-User License Agreement (EULA).
        """
        try:
            with open(EULA_FILE, 'r', encoding='utf8') as f:
                return f.read()
        except FileNotFoundError:
            pass

    @api_method(TrueNASIsEulaAcceptedArgs, TrueNASIsEulaAcceptedResult, cli_private=True, roles=['READONLY_ADMIN'])
    def is_eula_accepted(self):
        """
        Returns whether the EULA is accepted or not.
        """
        return not os.path.exists(EULA_PENDING_PATH)

    @api_method(TrueNASAcceptEulaArgs, TrueNASAcceptEulaResult, roles=['FULL_ADMIN'])
    def accept_eula(self):
        """
        Accept TrueNAS EULA.
        """
        try:
            os.unlink(EULA_PENDING_PATH)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

    @private
    def unaccept_eula(self):
        with open(EULA_PENDING_PATH, "w") as f:
            os.fchmod(f.fileno(), 0o600)

    @api_method(TrueNASIsProductionArgs, TrueNASIsProductionResult, roles=['READONLY_ADMIN'])
    async def is_production(self):
        """
        Returns if system is marked as production.
        """
        return await self.middleware.call('keyvalue.get', 'truenas:production', False)

    @api_method(TrueNASSetProductionArgs, TrueNASSetProductionResult, roles=['FULL_ADMIN'])
    @job()
    async def set_production(self, job, production, attach_debug):
        """
        Sets system production state and optionally sends initial debug.
        """
        was_production = await self.is_production()
        await self.middleware.call('keyvalue.set', 'truenas:production', production)

        if not was_production and production:
            serial = (await self.middleware.call('system.dmidecode_info'))["system-serial-number"]
            return await job.wrap(await self.middleware.call('support.new_ticket', {
                "title": f"System has been just put into production ({serial})",
                "body": "This system has been just put into production",
                "attach_debug": attach_debug,
                "category": "Installation/Setup",
                "criticality": "Inquiry",
                "environment": "Production",
                "name": "Automatic Alert",
                "email": "auto-support@ixsystems.com",
                "phone": "-",
            }))
