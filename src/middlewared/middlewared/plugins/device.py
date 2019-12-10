import asyncio
import os
import socket

from middlewared.schema import accepts, Str
from middlewared.service import private, Service

DEVD_SOCKETFILE = '/var/run/devd.pipe'


class DeviceService(Service):

    @accepts(Str('type', enum=['SERIAL', 'DISK']))
    async def get_info(self, _type):
        """
        Get info for SERIAL/DISK device types.
        """
        return await self.middleware.call(f'device.get_{_type.lower()}s')

    @private
    async def get_valid_zfs_partition_type_uuids(self):
        # https://salsa.debian.org/debian/gdisk/blob/master/parttypes.cc for valid zfs types
        # 516e7cba was being used by freebsd and 6a898cc3 is being used by linux
        return [
            '6a898cc3-1dd2-11b2-99a6-080020736631',
            '516e7cba-6ecf-11d6-8ff8-00022d09712b',
        ]

    @private
    async def get_valid_swap_partition_type_uuids(self):
        return ['516e7cb5-6ecf-11d6-8ff8-00022d09712b']


async def devd_loop(middleware):
    while True:
        try:
            if not os.path.exists(DEVD_SOCKETFILE):
                await asyncio.sleep(1)
                continue
            await devd_listen(middleware)
        except ConnectionRefusedError:
            middleware.logger.warn('devd connection refused, retrying...')
        except OSError:
            middleware.logger.warn('devd pipe error, retrying...', exc_info=True)
        await asyncio.sleep(1)


def parse_devd_message(msg):
    """
    Parse devd messages using "=" char as separator.
    We use the first word before "=" as key and every word minus 1 after "=" as value.
    The caveat is that we cant properly parse messages containing "=" in the value,
    however this seems good enough until kernel/devd can provide structured messages.
    """
    parsed = {}
    parts = msg.strip().split('=')
    for idx in range(len(parts) - 1):
        key = parts[idx].rsplit(' ', 1)[-1]
        value = parts[idx + 1].rsplit(' ', 1)[0].strip()
        parsed[key] = value
    return parsed


async def devd_listen(middleware):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(DEVD_SOCKETFILE)
    reader, writer = await asyncio.open_unix_connection(sock=s)

    while True:
        line = await reader.readline()
        line = line.decode(errors='ignore')
        if line == "":
            break

        if not line.startswith('!'):
            # TODO: its not a complete message, ignore for now
            continue

        try:
            parsed = await middleware.run_in_thread(parse_devd_message, line[1:])
        except Exception:
            middleware.logger.warn(f'Failed to parse devd message: {line}')
            continue

        if 'system' not in parsed:
            continue

        # Lets ignore CAM messages for now
        if parsed['system'] in ('CAM', 'ACPI'):
            continue

        await middleware.call_hook(
            f'devd.{parsed["system"]}'.lower(), data=parsed,
        )


def setup(middleware):
    asyncio.ensure_future(devd_loop(middleware))
