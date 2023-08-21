from subprocess import run, DEVNULL
from functools import cache

from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, List, Password, returns, Str
from middlewared.service import CallError, CRUDService, filterable, ValidationErrors
from middlewared.utils import filter_list
from middlewared.validators import Netmask, PasswordComplexity, Range


@cache
def lan_channels():
    channels = []
    out = run(['bmc-info', '--get-channel-info'], capture_output=True)
    lines = out.stdout.decode().split('\n')
    for idx, line in filter(lambda x: x[1], enumerate(lines)):
        # lines that we're interested in look like
        # Channel : 1
        # Medium Type : 802.3 LAN
        if (key_value := line.split(':')) and len(key_value) == 2 and '802.3 LAN' in key_value[1]:
            try:
                channels.append(int(lines[idx - 1].split(':')[-1].strip()))
            except (IndexError, ValueError):
                continue

    return channels


class IPMILanService(CRUDService):

    class Config:
        namespace = 'ipmi.lan'
        cli_namespace = 'network.ipmi'

    @accepts()
    @returns(List('lan_channels', items=[Int('lan_channel')]))
    def channels(self):
        """Return a list of available IPMI channels."""
        channels = []
        if self.middleware.call_sync('ipmi.is_loaded') and (channels := lan_channels()):
            if self.middleware.call_sync('truenas.get_chassis_hardware').startswith('TRUENAS-F'):
                # We cannot expose IPMI lan channel 8 on the f-series platform
                channels = [i for i in channels if i != 8]

        return channels

    @filterable
    def query(self, filters, options):
        """Query available IPMI Channels with `query-filters` and `query-options`."""
        result = []
        for channel in self.channels():
            section = 'Lan_Conf' if channel == 1 else f'Lan_Conf_Channel_{channel}'
            cp = run(['ipmi-config', '--checkout', f'--section={section}', '--verbose'], capture_output=True)
            if cp.returncode != 0 and (stderr := cp.stderr.decode()):
                # on the F-series platform, if you add the --verbose flag, then the return code is
                # set to 1 but the correct information is given to stdout. Just check to see if there
                # is stderr
                # TODO: fix this in dragonfish (dependent on webUI changes to be made see NAS-123225)
                # raise CallError(f'Failed to get details from channel {channel}: {stderr}')
                self.logger.error('Failed to get details from channel %r with error %r', channel, stderr)

            stdout = cp.stdout.decode().split('\n')
            if not stdout:
                continue

            data = {'channel': channel, 'id': channel}
            for i in filter(lambda x: x.startswith('\t') and not x.startswith('\t#'), stdout):
                try:
                    name, value = i.strip().split()
                    name, value = name.lower(), value.lower()
                    if value in ('no', 'yes'):
                        value = True if value == 'yes' else False
                    elif value.isdigit():
                        value = int(value)

                    data[name] = value
                except ValueError:
                    break

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
            Int('vlan', validators=[Range(0, 4094)], null=True),
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
        if not self.middleware.call_sync('ipmi.is_loaded'):
            verrors.add('ipmi.update', '/dev/ipmi0 could not be found')
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
            rc |= run(get_cmd(['dhcp']), **options).returncode
        else:
            rc |= run(get_cmd(['ipsrc', 'static']), **options).returncode
            rc |= run(get_cmd(['ipaddr', data['ipaddress']]), **options).returncode
            rc |= run(get_cmd(['netmask', data['netmask']]), **options).returncode
            rc |= run(get_cmd(['defgw', 'ipaddr', data['gateway']]), **options).returncode

        rc |= run(get_cmd(['vlan', 'id', f'{data.get("vlan", "off")}']), **options).returncode

        rc |= run(get_cmd(['access', 'on']), **options).returncode
        rc |= run(get_cmd(['auth', 'USER', 'MD2,MD5']), **options).returncode
        rc |= run(get_cmd(['auth', 'OPERATOR', 'MD2,MD5']), **options).returncode
        rc |= run(get_cmd(['auth', 'ADMIN', 'MD2,MD5']), **options).returncode
        rc |= run(get_cmd(['auth', 'CALLBACK', 'MD2,MD5']), **options).returncode

        # Apparently tickling these ARP options can "fail" on certain hardware
        # which isn't fatal so we ignore returncode in this instance. See #15578.
        run(get_cmd(['arp', 'respond', 'on']), **options)
        run(get_cmd(['arp', 'generate', 'on']), **options)

        if passwd := data.get('password'):
            cp = run(['ipmitool', 'user', 'set', 'password', '2', passwd], capture_output=True)
            if cp.returncode != 0:
                err = '\n'.join(cp.stderr.decode().split('\n'))
                raise CallError(f'Failed setting password: {err!r}')

        cp = run(['ipmitool', 'user', 'enable', '2'], capture_output=True)
        if cp.returncode != 0:
            err = '\n'.join(cp.stderr.decode().split('\n'))
            raise CallError(f'Failed enabling user: {err!r}')

        return rc
