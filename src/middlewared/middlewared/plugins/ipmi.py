import os
from subprocess import run as sync_run, DEVNULL

from middlewared.plugins.ipmi_.utils import parse_ipmitool_output
from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, List, Patch, Password, returns, Str
from middlewared.service import CallError, CRUDService, filterable, ValidationErrors
from middlewared.utils import filter_list, run
from middlewared.validators import Netmask, PasswordComplexity, Range

IPMI_DEV = '/dev/ipmi0'


class IPMIService(CRUDService):

    class Config:
        cli_namespace = 'network.ipmi'

    CHANNELS = None
    ENTRY = Patch(
        'ipmi_update', 'ipmi_entry',
        ('add', Int('id', required=True)),
        ('add', Int('channel', required=True)),
    )

    @accepts()
    @returns(Bool('ipmi_loaded'))
    def is_loaded(self):
        """Returns a boolean value indicating if `IPMI_DEV` is loaded."""
        return os.path.exists(IPMI_DEV)

    @accepts()
    @returns(List('ipmi_channels', items=[Int('ipmi_channel')]))
    def channels(self):
        """Return a list of available IPMI channels."""
        if not self.is_loaded():
            return []
        elif self.CHANNELS is None:
            self.CHANNELS = []
            for i in range(1, 17):
                rc = sync_run(['ipmitool', 'lan', 'print', f'{i}'], stdout=DEVNULL, stderr=DEVNULL).returncode
                if rc == 0:
                    self.CHANNELS.append(i)
                else:
                    # no reason to continue to check the other channel numbers
                    break

        return self.CHANNELS

    @filterable
    def query(self, filters, options):
        """Query available IPMI Channels with `query-filters` and `query-options`."""
        result = []
        for channel in self.channels():
            cp = run(['ipmitool', 'lan', 'print', f'{channel}'], capture_output=True)
            if cp.returncode != 0:
                raise CallError(f'Failed to get details from channel {channel}: {cp.stderr}')

            data = {'channel': channel, 'id': channel}
            for line in filter(lambda x: ':' in line, cp.stdout.decode().split('\n')):
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

    @accepts(Int('channel'), Dict(
        'ipmi_update',
        IPAddr('ipaddress', v6=False),
        Str('netmask', validators=[Netmask(ipv6=False, prefix_length=False)]),
        IPAddr('gateway', v6=False),
        Password('password', validators=[
            PasswordComplexity(["ASCII_UPPER", "ASCII_LOWER", "DIGIT", "SPECIAL"], 3),
            Range(8, 16)
        ]),
        Bool('dhcp'),
        Int('vlan', null=True),
        register=True
    ))
    async def do_update(self, id, data):
        """
        Update `id` IPMI Configuration.

        `ipaddress` is a valid ip which will be used to connect to the IPMI interface.

        `netmask` is the subnet mask associated with `ipaddress`.

        `dhcp` is a boolean value which if unset means that `ipaddress`, `netmask` and `gateway` must be set.
        """

        if not await self.middleware.call('ipmi.is_loaded'):
            raise CallError('The ipmi device could not be found')

        verrors = ValidationErrors()

        if not data.get('dhcp'):
            for k in ['ipaddress', 'netmask', 'gateway']:
                if not data.get(k):
                    verrors.add(
                        f'ipmi_update.{k}',
                        'This field is required when dhcp is not given'
                    )

        if verrors:
            raise verrors

        args = ['ipmitool', 'lan', 'set', str(id)]
        rv = 0
        if data.get('dhcp'):
            rv |= (await run(*args, 'ipsrc', 'dhcp', check=False)).returncode
        else:
            rv |= (await run(*args, 'ipsrc', 'static', check=False)).returncode
            rv |= (await run(*args, 'ipaddr', data['ipaddress'], check=False)).returncode
            rv |= (await run(*args, 'netmask', data['netmask'], check=False)).returncode
            rv |= (await run(*args, 'defgw', 'ipaddr', data['gateway'], check=False)).returncode
        rv |= (await run(
            *args, 'vlan', 'id', str(data['vlan']) if data.get('vlan') else 'off'
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
                'ipmitool', 'user', 'set', 'password', '2', data.get('password'),
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
    @returns()
    async def identify(self, options):
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

    # TODO: Document me as well please
    @filterable
    async def query_sel(self, filters, options):
        """
        Query IPMI System Event Log
        """
        return filter_list([
            record._asdict()
            for record in parse_ipmitool_output(await run('ipmitool', '-c', 'sel', 'elist'))
        ], filters, options)

    @accepts()
    @returns()
    async def clear_sel(self):
        """
        Clear IPMI System Event Log
        """
        await run('ipmitool', 'sel', 'clear')
