from __future__ import annotations

import errno
import os
from typing import TYPE_CHECKING

from ixhardware import TRUENAS_UNKNOWN, get_chassis_hardware as _get_chassis_hardware

from middlewared.api.current import SupportNewTicket, TruecommandStatus
from middlewared.service import ServiceContext

if TYPE_CHECKING:
    from middlewared.job import Job


EULA_FILE = '/usr/local/share/truenas/eula.html'
EULA_PENDING_PATH = '/data/truenas-eula-pending'


async def managed_by_truecommand(context: ServiceContext) -> bool:
    return TruecommandStatus(
        (await context.middleware.call('truecommand.config'))['status']
    ) == TruecommandStatus.CONNECTED


def get_chassis_hardware() -> str:
    result: str = _get_chassis_hardware()
    return result


async def is_ix_hardware(context: ServiceContext) -> bool:
    return bool(await context.to_thread(get_chassis_hardware) != TRUENAS_UNKNOWN)


def get_eula() -> str | None:
    try:
        with open(EULA_FILE, 'r', encoding='utf8') as f:
            return f.read()
    except FileNotFoundError:
        return None


def is_eula_accepted() -> bool:
    return not os.path.exists(EULA_PENDING_PATH)


def accept_eula() -> None:
    try:
        os.unlink(EULA_PENDING_PATH)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise


def unaccept_eula() -> None:
    with open(EULA_PENDING_PATH, 'w') as f:
        os.fchmod(f.fileno(), 0o600)


async def is_production(context: ServiceContext) -> bool:
    return await context.call2(context.s.keyvalue.get, 'truenas:production', False)


async def set_production(
    context: ServiceContext, job: Job, production: bool, attach_debug: bool,
) -> SupportNewTicket | None:
    was_production = await is_production(context)
    await context.call2(context.s.keyvalue.set, 'truenas:production', production)

    if not was_production and production:
        serial = (await context.middleware.call('system.dmidecode_info'))['system-serial-number']
        result: SupportNewTicket = await job.wrap(await context.middleware.call('support.new_ticket', {
            'title': f'System has been just put into production ({serial})',
            'body': 'This system has been just put into production',
            'attach_debug': attach_debug,
            'category': 'Installation/Setup',
            'criticality': 'Inquiry',
            'environment': 'Production',
            'name': 'Automatic Alert',
            'email': 'auto-support@truenas.com',
            'phone': '-',
        }))
        return result
    return None
