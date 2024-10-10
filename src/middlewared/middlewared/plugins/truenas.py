import errno
import os

from ixhardware import TRUENAS_UNKNOWN, get_chassis_hardware

from middlewared.plugins.truecommand.enums import Status as TrueCommandStatus
from middlewared.schema import accepts, Bool, Patch, returns, Str
from middlewared.service import cli_private, job, no_auth_required, private, Service
from middlewared.utils.functools_ import cache

EULA_FILE = '/usr/local/share/truenas/eula.html'
EULA_PENDING_PATH = "/data/truenas-eula-pending"


class TrueNASService(Service):

    class Config:
        cli_namespace = 'system.truenas'

    @no_auth_required
    @accepts()
    @returns(Bool())
    async def managed_by_truecommand(self):
        """
        Returns whether TrueNAS is being managed by TrueCommand or not.

        This endpoint has no authentication required as it is used by UI when the user has not logged in to see
        if the system is being managed by TrueCommand or not.
        """
        return TrueCommandStatus(
            (await self.middleware.call('truecommand.config'))['status']
        ) == TrueCommandStatus.CONNECTED

    @accepts()
    @returns(Str('system_chassis_hardware'))
    @cli_private
    @cache
    async def get_chassis_hardware(self):
        """
        Returns what type of hardware this is, detected from dmidecode.
        """
        dmi = await self.middleware.call('system.dmidecode_info_internal')
        return get_chassis_hardware(dmi)

    @accepts(roles=['READONLY_ADMIN'])
    @returns(Bool('is_ix_hardware'))
    async def is_ix_hardware(self):
        """
        Return a boolean value on whether this is hardware that iXsystems sells.
        """
        return await self.get_chassis_hardware() != TRUENAS_UNKNOWN

    @accepts(roles=['READONLY_ADMIN'])
    @returns(Str('eula', max_length=None, null=True))
    @cli_private
    def get_eula(self):
        """
        Returns the TrueNAS End-User License Agreement (EULA).
        """
        try:
            with open(EULA_FILE, 'r', encoding='utf8') as f:
                return f.read()
        except FileNotFoundError:
            pass

    @accepts(roles=['READONLY_ADMIN'])
    @returns(Bool('system_eula_accepted'))
    @cli_private
    def is_eula_accepted(self):
        """
        Returns whether the EULA is accepted or not.
        """
        return not os.path.exists(EULA_PENDING_PATH)

    @accepts()
    @returns()
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

    @accepts(roles=['READONLY_ADMIN'])
    @returns(Bool('is_production_system'))
    async def is_production(self):
        """
        Returns if system is marked as production.
        """
        return await self.middleware.call('keyvalue.get', 'truenas:production', False)

    @accepts(Bool('production'), Bool('attach_debug', default=False))
    @returns(Patch(
        'new_ticket_response', 'set_production',
        ('attr', {'null': True}),
    ))
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
