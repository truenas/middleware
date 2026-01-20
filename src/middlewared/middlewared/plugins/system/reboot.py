import enum

from middlewared.api import api_method
from middlewared.api.current import SystemRebootInfoArgs, SystemRebootInfoResult
from middlewared.service import private, Service


class RebootReason(enum.Enum):
    # Ensure when a reason is added here, we update disabled reasons in HA to account for the new/removed knob
    FIPS = 'FIPS configuration was changed.'
    GPOSSTIG = 'General Purpose OS STIG configuration was changed.'
    UPGRADE = 'This system needs to be rebooted in order for the system upgrade to finish.'


class SystemRebootService(Service):

    class Config:
        cli_namespace = 'system.reboot_required'
        namespace = 'system.reboot'

    reboot_reasons : dict[str, str] = {}

    @api_method(SystemRebootInfoArgs, SystemRebootInfoResult, roles=['SYSTEM_GENERAL_READ'])
    async def info(self):
        return {
            'boot_id': await self.middleware.call('system.boot_id'),
            'reboot_required_reasons': [
                {
                    'code': code,
                    'reason': reason,
                }
                for code, reason in self.reboot_reasons.items()
            ],
        }

    @private
    async def add_reason(self, code: str, reason: str):
        """
        Adds a reason for why this system needs a reboot.
        :param code: unique identifier for the reason.
        :param reason: text explanation for the reason.
        """
        self.reboot_reasons[code] = reason

        await self._send_event()

    @private
    async def toggle_reason(self, code: str, reason: str):
        """
        Adds a reason for why this system needs a reboot if it does not exist, removes it otherwise.
        :param code: unique identifier for the reason.
        :param reason: text explanation for the reason.
        """
        if code in self.reboot_reasons:
            self.reboot_reasons.pop(code)
        else:
            self.reboot_reasons[code] = reason

        await self._send_event()

    @private
    async def list_reasons(self):
        """
        List reasons code for why this system needs a reboot.
        :return: a list of reason codes
        """
        return list(self.reboot_reasons.keys())

    @private
    async def remove_reason(self, code: str):
        """
        Removes a reason for why this system needs a reboot.
        :param code: unique identifier for the reason that was used to add it.
        """
        self.reboot_reasons.pop(code, None)

        await self._send_event()

    async def _send_event(self):
        self.middleware.send_event('system.reboot.info', 'CHANGED', id=None, fields=await self.info())


async def setup(middleware):
    middleware.event_register('system.reboot.info', 'Sent when a system reboot is required.',
                              roles=['SYSTEM_GENERAL_READ'])
