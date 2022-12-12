import asyncio
import os

from middlewared.service import private, Service

DEVD_CONNECTED = False
DEVD_SOCKETFILE = '/var/run/devd.pipe'


class DeviceService(Service):
    @private
    async def devd_connected(self):
        return DEVD_CONNECTED


async def devd_loop(middleware):
    while True:
        try:
            if not os.path.exists(DEVD_SOCKETFILE):
                middleware.logger.info('devd is not running yet, waiting...')
                await asyncio.sleep(1)
                continue
            await devd_listen(middleware)
        except ConnectionRefusedError:
            middleware.logger.warn('devd connection refused, retrying...')
        except Exception:
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
    global DEVD_CONNECTED

    reader, writer = await asyncio.open_unix_connection(path=DEVD_SOCKETFILE)
    try:
        middleware.logger.info('devd connection established')
        DEVD_CONNECTED = True

        while True:
            line = await reader.readline()
            line = line.decode(errors='ignore')
            if line == "":
                break

            if not line.startswith('!'):
                # TODO: its not a complete message, ignore for now
                continue

            try:
                parsed = parse_devd_message(line[1:])
            except Exception:
                middleware.logger.warn(f'Failed to parse devd message: {line}')
                continue

            if 'system' not in parsed:
                continue

            # Lets ignore CAM messages for now
            if parsed['system'] in ('CAM', 'ACPI'):
                continue

            if parsed['type'] == 'GEOM::physpath' and parsed.get('devname'):
                # treat GEOM::physpath as DEVFS (even though it's geom)
                # to fix a rare race condition between CAM and SES drivers
                # when disks are moved around
                # (This was seen when QE team was testing new "Phison" SSDS
                #   and moving them around between head-unit and jbods)
                parsed = {'type': 'CREATE', 'system': 'DEVFS', 'subsystem': 'CDEV', 'cdev': parsed['devname']}

            await middleware.call_hook(f'devd.{parsed["system"]}'.lower(), data=parsed)
    finally:
        DEVD_CONNECTED = False
        writer.close()
        await writer.wait_closed()


def setup(middleware):
    middleware.create_task(devd_loop(middleware))
