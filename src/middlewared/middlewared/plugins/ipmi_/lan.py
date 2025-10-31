from subprocess import run, DEVNULL
from functools import cache

from middlewared.api import api_method
from middlewared.api.current import (
    IPMILanEntry,
    IPMILanChannelsArgs,
    IPMILanChannelsResult,
    IPMILanUpdateArgs,
    IPMILanUpdateResult,
    IPMILanQueryArgs,
    IPMILanQueryResult,
)
from middlewared.service import (
    private,
    CallError,
    Service,
    ValidationError,
    ValidationErrors,
)
from middlewared.utils.filter_list import filter_list


@cache
def lan_channels() -> tuple[int]:
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

    return tuple(channels)


def apply_config(channel, data):
    base_cmd = ['ipmitool', 'lan', 'set', str(channel)]

    rc = 0
    options = {'stdout': DEVNULL, 'stderr': DEVNULL}
    if data['dhcp']:
        rc |= run(base_cmd + ['ipsrc', 'dhcp'], **options).returncode
    else:
        rc |= run(base_cmd + ['ipsrc', 'static'], **options).returncode
        rc |= run(base_cmd + ['ipaddr', data['ipaddress']], **options).returncode
        rc |= run(base_cmd + ['netmask', data['netmask']], **options).returncode
        rc |= run(base_cmd + ['defgw', 'ipaddr', data['gateway']], **options).returncode

    vlan = data["vlan"]
    if vlan is None:
        vlan = "off"
    rc |= run(base_cmd + ['vlan', 'id', str(vlan)], **options).returncode

    rc |= run(base_cmd + ['access', 'on'], **options).returncode
    rc |= run(base_cmd + ['auth', 'USER', 'MD2,MD5'], **options).returncode
    rc |= run(base_cmd + ['auth', 'OPERATOR', 'MD2,MD5'], **options).returncode
    rc |= run(base_cmd + ['auth', 'ADMIN', 'MD2,MD5'], **options).returncode
    rc |= run(base_cmd + ['auth', 'CALLBACK', 'MD2,MD5'], **options).returncode

    # Apparently tickling these ARP options can "fail" on certain hardware
    # which isn't fatal so we ignore returncode in this instance. See #15578.
    run(base_cmd + ['arp', 'respond', 'on'], **options)
    run(base_cmd + ['arp', 'generate', 'on'], **options)

    if passwd := data['password']:
        cp = run(['ipmitool', 'user', 'set', 'password', '2', passwd], capture_output=True)
        if cp.returncode != 0:
            err = '\n'.join(cp.stderr.decode().split('\n'))
            raise CallError(f'Failed setting password: {err!r}')

    cp = run(['ipmitool', 'user', 'enable', '2'], capture_output=True)
    if cp.returncode != 0:
        err = '\n'.join(cp.stderr.decode().split('\n'))
        raise CallError(f'Failed enabling user: {err!r}')

    return rc


class IPMILanService(Service):

    class Config:
        namespace = 'ipmi.lan'
        cli_namespace = 'network.ipmi'
        role_prefix = 'IPMI'
        entry = IPMILanEntry

    @api_method(
        IPMILanChannelsArgs,
        IPMILanChannelsResult,
        roles=['IPMI_READ'],
    )
    def channels(self):
        """Return a list of available IPMI channels."""
        channels = []
        if self.middleware.call_sync('ipmi.is_loaded') and (channels := lan_channels()):
            if self.middleware.call_sync('truenas.get_chassis_hardware').startswith('TRUENAS-F'):
                # We cannot expose IPMI lan channel 8 on the f-series platform
                channels = [i for i in channels if i != 8]

        return list(channels)

    @private
    def query_impl(self):
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

            data = {'channel': channel, 'id': channel, 'vlan_id_enable': False}
            for line in filter(lambda x: x.startswith('\t') and not x.startswith('\t#'), stdout):
                try:
                    name, value = line.strip().split()
                    name, value = name.lower(), value.lower()
                    if value in ('no', 'yes'):
                        value = True if value == 'yes' else False
                    elif value.isdigit():
                        value = int(value)

                    data[name] = value
                except ValueError:
                    break

            if data['vlan_id_enable'] is False:
                data['vlan_id'] = None

            result.append(data)

        return result

    @api_method(
        IPMILanQueryArgs,
        IPMILanQueryResult,
        roles=['IPMI_READ'],
    )
    def query(self, data):
        """Query available IPMI Channels with `query-filters` and `query-options`."""
        result = []
        if not data['ipmi-options']['query-remote']:
            result = self.query_impl()
        elif self.middleware.call_sync('failover.licensed'):
            try:
                result = self.middleware.call_sync(
                    'failover.call_remote', 'ipmi.lan.query_impl'
                )
            except Exception:
                # could be ENOMETHOD on upgrade or could be that
                # remote node isn't connected/functioning etc OR
                # could be that we're not on an HA system. In
                # either of the scenarios, we just need to return
                # an empty list
                result = []

        return filter_list(result, data['query-filters'], data['query-options'])

    @api_method(
        IPMILanUpdateArgs,
        IPMILanUpdateResult,
        roles=['IPMI_WRITE'],
        audit='Update IPMI configuration'
    )
    def update(self, id_, data):
        """Update IPMI channel configuration"""
        verrors = ValidationErrors()
        schema = 'ipmi.lan.update'
        if not self.middleware.call_sync('ipmi.is_loaded'):
            verrors.add(schema, '/dev/ipmi0 could not be found')
        elif id_ not in self.channels():
            verrors.add(schema, f'IPMI channel number {id_!r} not found')
        verrors.check()

        # It's _very_ important to pop this key so that
        # we don't have a situation where we send the same
        # data across to the other side which turns around
        # and sends it back to us causing a loop
        apply_remote = data.pop('apply_remote')
        if not apply_remote:
            return apply_config(id_, data)
        elif self.middleware.call_sync('failover.licensed'):
            try:
                return self.middleware.call_sync('failover.call_remote', 'ipmi.lan.update', [id_, data])
            except Exception as e:
                raise ValidationError(schema, f'Failed to apply IPMI config on remote controller: {e}')
