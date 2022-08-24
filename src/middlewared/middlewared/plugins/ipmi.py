import os
from subprocess import run, DEVNULL

from middlewared.plugins.ipmi_.utils import parse_ipmitool_output
from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, List, Patch, Password, returns, Str
from middlewared.service import CallError, CRUDService, filterable, filterable_returns, ValidationErrors, job
from middlewared.utils import filter_list
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
                rc = run(['ipmitool', 'lan', 'print', f'{i}'], stdout=DEVNULL, stderr=DEVNULL).returncode
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

    @accepts(
        Int('channel'),
        Dict(
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
        )
    )
    def do_update(self, id, data):
        """
        Update IPMI configuration on channel number `id`.

        `ipaddress` is an IPv4 address to be assigned to channel number `id`.
        `netmask` is the subnet mask associated with `ipaddress`.
        `gateway` is an IPv4 address used by `ipaddress` to reach outside the local subnet.
        `password` is a password to be assigned to channel number `id`
        `dhcp` is a boolean. If False, `ipaddress`, `netmask` and `gateway` must be set.
        `vlan` is an integer representing the vlan tag number.
        """
        verrors = ValidationErrors()
        if not self.is_loaded():
            verrors.add('ipmi.update', f'{IPMI_DEV!r} could not be found')
        elif id not in self.channels():
            verrors.add('ipmi.update', f'IPMI channel number {id!r} not found')
        elif not data.get('dhcp'):
            for k in ['ipaddress', 'netmask', 'gateway']:
                if not data.get(k):
                    verrors.add(f'ipmi_update.{k}', 'This field is required when dhcp is false.')
        verrors.check()

        def get_cmd(cmds):
            nonlocal id
            return ['ipmitool', 'lan', 'set', f'{id}'] + cmds

        rc = 0
        options = {'stdout': DEVNULL, 'stderr': DEVNULL}
        if data.get('dhcp'):
            rc |= run(get_cmd(id, ['dhcp']), **options).returncode
        else:
            rc |= run(get_cmd(['ipsrc', 'static'], **options)).returncode
            rc |= run(get_cmd(['ipaddr', data['ipaddress']], **options)).returncode
            rc |= run(get_cmd(['netmask', data['netmask']], **options)).returncode
            rc |= run(get_cmd(['defgw', 'ipaddr', data['gateway']], **options)).returncode

        rc |= run(get_cmd(['vlan', 'id', f'{data.get("vlan", "off")}'], **options)).returncode

        rc |= run(get_cmd(['access', 'on'], **options)).returncode
        rc |= run(get_cmd(['auth', 'USER', 'MD2,MD5'], **options)).returncode
        rc |= run(get_cmd(['auth', 'OPERATOR', 'MD2,MD5'], **options)).returncode
        rc |= run(get_cmd(['auth', 'ADMIN', 'MD2,MD5'], **options)).returncode
        rc |= run(get_cmd(['auth', 'CALLBACK', 'MD2,MD5'], **options)).returncode

        # Apparently tickling these ARP options can "fail" on certain hardware
        # which isn't fatal so we ignore returncode in this instance. See #15578.
        run(get_cmd(['arp', 'respond', 'on'], **options))
        run(get_cmd(['arp', 'generate', 'on'], **options))

        if passwd := data.get('password'):
            cp = run(get_cmd(['ipmitool', 'user', 'set', 'password', '2', passwd]), capture_output=True)
            if cp.returncode != 0:
                raise CallError(f'Failed setting password: {cp.stderr!r}')

        cp = run(get_cmd(['ipmitool', 'user', 'enable', '2']), capture_output=True)
        if cp.returncode != 0:
            raise CallError(f'Failed enabling user: {cp.stderr!r}')

        return rc

    @accepts(Dict(
        'options',
        Int('seconds', default=15, validators=[Range(min=0, max=3600)]),
        Bool('force', default=False),
    ))
    @returns()
    def identify(self, options):
        """
        Turn on chassis identify light.

        `seconds` is an integer representing the number of seconds to leave the chassis identify light turned on.
            - default is 15 seconds
            - to turn it off, specify `seconds` as 0
        `force` is a boolean. When True, turn on chassis identify light indefinitely.
        """
        verrors = ValidationErrors()
        force = options['force']
        seconds = options["seconds"]
        if force and seconds:
            verrors.add('ipmi.identify', f'Seconds: ({seconds}) and Force: ({force}) are exclusive.')
        verrors.check()

        run(['ipmitool', 'chassis', 'identify', 'force' if force else seconds], stdout=DEVNULL, stderr=DEVNULL)

    @filterable
    @filterable_returns(List('events_log', items=[Dict('event', additional_attrs=True)]))
    @job(lock='query_sel', lock_queue_size=3)
    def query_sel(self, job, filters, options):
        """Query IPMI system extended event log."""
        results = []
        cp = run(['ipmitool', '-c', 'sel', 'elist'], capture_output=True)  # this is slowwww
        if cp.returncode == 0 and cp.stdout:
            for record in parse_ipmitool_output(cp.stdout.decode()):
                results.append(record._asdict())

        return filter_list(results, filters, options)

    @accepts()
    @returns()
    def clear_sel(self):
        """Clear IPMI system event log."""
        run(['ipmitool', 'sel', 'clear'], stdout=DEVNULL, stderr=DEVNULL)
