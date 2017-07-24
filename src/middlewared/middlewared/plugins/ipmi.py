from bsd import kld

from middlewared.schema import Bool, Dict, Int, Str, accepts
from middlewared.service import CallError, Service, filterable
from middlewared.utils import filter_list, run

import errno
import os
import pipes
import subprocess

channels = []


class IPMIService(Service):

    @accepts()
    async def is_loaded(self):
        return os.path.exists('/dev/ipmi0')

    @accepts()
    async def channels(self):
        """
        Return a list with the IPMI channels available.
        """
        return channels

    @filterable
    async def query(self, filters=None, options=None):
        result = []
        for channel in await self.channels():
            try:
                cp = await run('ipmitool', 'lan', 'print', str(channel))
            except subprocess.CalledProcessError as e:
                raise CallError(f'Failed to get details from channel {channel}: {e}')

            output = cp.stdout.decode()
            data = {'channel': channel}
            for line in output.split('\n'):
                if ':' not in line:
                    continue

                name, value = line.split(':', 1)
                if not name:
                    continue

                name = name.strip()
                value = value.strip()

                if name == 'IP Address':
                    data['ipaddress'] = value
                elif name == 'Subnet Mask':
                    data['netmask'] = value
                elif name == 'Default Gateway IP':
                    data['gateway'] = value
                elif name == '802.1q VLAN ID':
                    if value == 'Disabled':
                        data['vlan'] = None
                    else:
                        data['vlan'] = value
                elif name == 'IP Address Source':
                    data['dhcp'] = False if value == 'Static Address' else True
            result.append(data)
        return filter_list(result, filters, options)

    @accepts(Dict(
        'ipmi',
        Int('channel', required=True),
        Str('ipaddress'),
        Str('netmask'),
        Str('gateway'),
        Str('password'),
        Bool('dhcp'),
        Int('vlan'),
    ))
    async def update(self, data):

        if not await self.is_loaded():
            raise CallError('The ipmi device could not be found')

        args = ['ipmitool', 'lan', 'set', str(data['channel'])]
        rv = 0
        if data.get('dhcp'):
            rv |= (await run(*args, 'ipsrc', 'dhcp', check=False)).returncode
        else:
            rv |= (await run(*args, 'ipsrc', 'static', check=False)).returncode
            rv |= (await run(*args, 'ipaddr', data['ipaddress'], check=False)).returncode
            rv |= (await run(*args, 'netmask', data['netmask'], check=False)).returncode
            rv |= (await run(*args, 'defgw', 'ipaddr', data['gateway'], check=False)).returncode
        rv |= (await run(
            *args, 'vlan', 'id', data['vlan'] if data.get('vlan') else 'off'
        )).returncode

        rv |= (await run(*args, 'access', 'on', check=False)).returncode
        rv |= (await run(*args, 'auth', 'USER', 'MD2,MD5', check=False)).returncode
        rv |= (await run(*args, 'auth', 'OPERATOR', 'MD2,MD5', check=False)).returncode
        rv |= (await run(*args, 'auth', 'ADMIN', 'MD2,MD5', check=False)).returncode
        rv |= (await run(*args, 'auth', 'CALLBACK', 'MD2,MD5', check=False)).returncode
        # Setting arp have some issues in some hardwares
        # Do not fail if setting these couple settings do not work
        # See #15578
        await run(*args, 'arp', 'respond', 'on', check=False)
        await run(*args, 'arp', 'generate', 'on', check=False)
        if data.get('password'):
            rv |= (await run(
                'ipmitool', 'user', 'set', 'password', '2',
                pipes.quote(data.get('password')),
            )).returncode
        rv |= (await run('ipmitool', 'user', 'enable', '2')).returncode
        # XXX: according to dwhite, this needs to be executed off the box via
        # the lanplus interface.
        # rv |= (await run('ipmitool', 'sol', 'set', 'enabled', 'true', '1')).returncode
        # )
        return rv

    @accepts(Dict(
        'options',
        Int('seconds'),
        Bool('force'),
    ))
    async def identify(self, options=None):
        """
        Turn on IPMI chassis identify light.

        To turn off specify 0 as `seconds`.
        """
        options = options or {}
        if options.get('force') and options.get('seconds'):
            raise CallError('You have to use either "seconds" or "force" option, not both')

        if options.get('force'):
            cmd = 'force'
        else:
            cmd = str(options.get('seconds'))
        await run('ipmitool', 'chassis', 'identify', cmd)


async def setup(middleware):

    try:
        kld.kldload('/boot/kernel/ipmi.ko')
    except OSError as e:
        # Only skip if not already loaded
        if e.errno != errno.EEXIST:
            middleware.logger.warn(f'Cannot load IPMI module: {e}')
            return

    # Scan available channels
    for i in range(1, 17):
        try:
            await run('/usr/local/bin/ipmitool', 'lan', 'print', str(i))
        except subprocess.CalledProcessError:
            continue
        channels.append(i)
