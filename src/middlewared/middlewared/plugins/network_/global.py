import ipaddress
import psutil
import contextlib
import signal

import middlewared.sqlalchemy as sa
from middlewared.service import ConfigService, private
from middlewared.schema import accepts, Patch, List, Dict, Int, Str, Bool, IPAddr, Ref, ValidationErrors
from middlewared.validators import Match, Hostname


class NetworkConfigurationModel(sa.Model):
    __tablename__ = 'network_globalconfiguration'

    id = sa.Column(sa.Integer(), primary_key=True)
    gc_hostname = sa.Column(sa.String(120), default='nas')
    gc_hostname_b = sa.Column(sa.String(120), nullable=True)
    gc_domain = sa.Column(sa.String(120), default='local')
    gc_ipv4gateway = sa.Column(sa.String(42), default='')
    gc_ipv6gateway = sa.Column(sa.String(45), default='')
    gc_nameserver1 = sa.Column(sa.String(45), default='')
    gc_nameserver2 = sa.Column(sa.String(45), default='')
    gc_nameserver3 = sa.Column(sa.String(45), default='')
    gc_httpproxy = sa.Column(sa.String(255))
    gc_netwait_enabled = sa.Column(sa.Boolean(), default=False)
    gc_netwait_ip = sa.Column(sa.String(300))
    gc_hosts = sa.Column(sa.Text(), default='')
    gc_domains = sa.Column(sa.Text(), default='')
    gc_service_announcement = sa.Column(sa.JSON(type=dict), default={'mdns': True, 'wsdd': True, "netbios": False})
    gc_hostname_virtual = sa.Column(sa.String(120), nullable=True)
    gc_activity = sa.Column(sa.JSON(type=dict))


class NetworkConfigurationService(ConfigService):
    class Config:
        namespace = 'network.configuration'
        datastore = 'network.globalconfiguration'
        datastore_prefix = 'gc_'
        datastore_extend = 'network.configuration.network_config_extend'
        cli_namespace = 'network.configuration'

    ENTRY = Dict(
        'network_configuration_entry',
        Int('id', required=True),
        Str('hostname', required=True, validators=[Hostname()]),
        Str('domain', validators=[Match(r'^[a-zA-Z\.\-\0-9]*$')],),
        IPAddr('ipv4gateway', required=True),
        IPAddr('ipv6gateway', required=True, allow_zone_index=True),
        IPAddr('nameserver1', required=True),
        IPAddr('nameserver2', required=True),
        IPAddr('nameserver3', required=True),
        Str('httpproxy', required=True),
        Bool('netwait_enabled', required=True),
        List('netwait_ip', required=True, items=[Str('netwait_ip')]),
        Str('hosts', required=True),
        List('domains', required=True, items=[Str('domain')]),
        Dict(
            'service_announcement',
            Bool('netbios'),
            Bool('mdns'),
            Bool('wsd'),
            register=True,
        ),
        Dict(
            'activity',
            Str('type', enum=['ALLOW', 'DENY'], required=True),
            List('activities', items=[Str('activity')]),
            strict=True
        ),
        Str('hostname_local', required=True, validators=[Hostname()]),
        Str('hostname_b', validators=[Hostname()], null=True),
        Str('hostname_virtual', validators=[Hostname()], null=True),
        Dict(
            'state',
            IPAddr('ipv4gateway', required=True),
            IPAddr('ipv6gateway', required=True, allow_zone_index=True),
            IPAddr('nameserver1', required=True),
            IPAddr('nameserver2', required=True),
            IPAddr('nameserver3', required=True),
        ),
    )

    @private
    def network_config_extend(self, data):
        # hostname_local will be used when the hostname of the current machine
        # needs to be used so it works with either TrueNAS SCALE or SCALE_ENTERPRISE
        data['hostname_local'] = data['hostname']

        if not self.middleware.call_sync('system.is_enterprise'):
            data.pop('hostname_b')
            data.pop('hostname_virtual')
        else:
            if self.middleware.call_sync('failover.node') == 'B':
                data['hostname_local'] = data['hostname_b']

        data['domains'] = data['domains'].split()
        data['netwait_ip'] = data['netwait_ip'].split()

        data['state'] = {
            'ipv4gateway': '',
            'ipv6gateway': '',
            'nameserver1': '',
            'nameserver2': '',
            'nameserver3': '',
        }
        summary = self.middleware.call_sync('network.general.summary')
        for default_route in summary['default_routes']:
            try:
                ipaddress.IPv4Address(default_route)
            except ValueError:
                if not data['state']['ipv6gateway']:
                    data['state']['ipv6gateway'] = default_route
            else:
                if not data['state']['ipv4gateway']:
                    data['state']['ipv4gateway'] = default_route
        for i, nameserver in enumerate(summary['nameservers'][:3]):
            data['state'][f'nameserver{i + 1}'] = nameserver

        return data

    @private
    async def validate_general_settings(self, data, schema):
        verrors = ValidationErrors()

        for key in [key for key in data.keys() if 'nameserver' in key]:
            nameserver_value = data.get(key)
            if nameserver_value:
                try:
                    nameserver_ip = ipaddress.ip_address(nameserver_value)
                except ValueError as e:
                    verrors.add(
                        f'{schema}.{key}',
                        str(e)
                    )
                else:
                    if nameserver_ip.is_loopback:
                        verrors.add(
                            f'{schema}.{key}',
                            'Loopback is not a valid nameserver'
                        )
                    elif nameserver_ip.is_unspecified:
                        verrors.add(
                            f'{schema}.{key}',
                            'Unspecified addresses are not valid as nameservers'
                        )
                    elif nameserver_ip.version == 4:
                        if nameserver_value == '255.255.255.255':
                            verrors.add(
                                f'{schema}.{key}',
                                'This is not a valid nameserver address'
                            )
                        elif nameserver_value.startswith('169.254'):
                            verrors.add(
                                f'{schema}.{key}',
                                '169.254/16 subnet is not valid for nameserver'
                            )

                    nameserver_number = int(key[-1])
                    for i in range(nameserver_number - 1, 0, -1):
                        if f'nameserver{i}' in data.keys() and not data[f'nameserver{i}']:
                            verrors.add(
                                f'{schema}.{key}',
                                f'Must fill out namserver{i} before filling out {key}'
                            )

        ipv4_gateway_value = data.get('ipv4gateway')
        if ipv4_gateway_value:
            if not await self.middleware.call(
                    'route.ipv4gw_reachable',
                    ipaddress.ip_address(ipv4_gateway_value).exploded
            ):
                verrors.add(
                    f'{schema}.ipv4gateway',
                    f'Gateway {ipv4_gateway_value} is unreachable'
                )

        netwait_ip = data.get('netwait_ip')
        if netwait_ip:
            for ip in netwait_ip:
                try:
                    ipaddress.ip_address(ip)
                except ValueError as e:
                    verrors.add(
                        f'{schema}.netwait_ip',
                        f'{e.__str__()}'
                    )

        if data.get('domains'):
            if len(data.get('domains')) > 5:
                verrors.add(
                    f'{schema}.domains',
                    'No more than 5 additional domains are allowed'
                )

        return verrors

    @accepts(Ref('service_announcement'))
    @private
    async def toggle_announcement(self, data):
        announce_srv = {'mdns': 'mdns', 'netbios': 'nmbd', 'wsd': 'wsdd'}
        for srv, enabled in data.items():
            service_name = announce_srv[srv]
            started = await self.middleware.call('service.started', service_name)
            verb = None

            if enabled:
                verb = 'restart' if started else 'start'
            else:
                verb = 'stop' if started else None

            if not verb:
                continue

            await self.middleware.call(f'service.{verb}', service_name)

    @accepts(
        Patch(
            'network_configuration_entry', 'global_configuration_update',
            ('rm', {'name': 'id'}),
            ('rm', {'name': 'hostname_local'}),
            ('rm', {'name': 'state'}),
            ('attr', {'update': True}),
        ),
    )
    async def do_update(self, data):
        """
        Update Network Configuration Service configuration.

        `ipv4gateway` if set is used instead of the default gateway provided by DHCP.

        `nameserver1` is primary DNS server.

        `nameserver2` is secondary DNS server.

        `nameserver3` is tertiary DNS server.

        `httpproxy` attribute must be provided if a proxy is to be used for network operations.

        `netwait_enabled` is a boolean attribute which when set indicates that network services will not start at
        boot unless they are able to ping the addresses listed in `netwait_ip` list.

        `service_announcement` determines the broadcast protocols that will be used to advertise the server.
        `netbios` enables the NetBIOS name server (NBNS), which starts concurrently with the SMB service. SMB clients
        will only perform NBNS lookups if SMB1 is enabled. NBNS may be required for legacy SMB clients.
        `mdns` enables multicast DNS service announcements for enabled services. `wsd` enables Web Service
        Discovery support.
        """
        config = await self.config()
        config.pop('state')

        new_config = config.copy()
        new_config.update(data)
        new_config['service_announcement'] = config['service_announcement'] | data.get('service_announcement', {})

        verrors = await self.validate_general_settings(data, 'global_configuration_update')

        filters = [('timemachine', '=', True), ('enabled', '=', True)]
        if not new_config['service_announcement']['mdns'] and await self.middleware.call('sharing.smb.query', filters):
            verrors.add(
                'global_configuration_update.service_announcement.mdns',
                'NAS is configured as a time machine target. mDNS is required.'
            )

        lhost_changed = config['hostname_local'] != new_config['hostname_local']
        bhost_changed = config.get('hostname_b') and config['hostname_b'] != new_config['hostname_b']
        vhost_changed = config.get('hostname_virtual') and config['hostname_virtual'] != new_config['hostname_virtual']

        if vhost_changed and await self.middleware.call('activedirectory.get_state') != "DISABLED":
            verrors.add(
                'global_configuration_update.hostname_virtual',
                'This parameter may not be changed after joining Active Directory (AD). '
                'If it must be changed, the proper procedure is to leave the AD domain '
                'and then alter the parameter before re-joining the domain.'
            )

        verrors.check()

        # pop the `hostname_local` key since that's created in the _extend method
        # and doesn't exist in the database
        new_config.pop('hostname_local', None)

        # normalize the `domains` and `netwait_ip` keys
        new_config['domains'] = ' '.join(new_config.get('domains', []))
        new_config['netwait_ip'] = ' '.join(new_config.get('netwait_ip', []))

        # update the db
        await self.middleware.call(
            'datastore.update', 'network.globalconfiguration', config['id'], new_config, {'prefix': 'gc_'}
        )

        domainname_changed = new_config['domain'] != config['domain']
        dnssearch_changed = new_config['domains'] != config['domains']
        dns1_changed = new_config['nameserver1'] != config['nameserver1']
        dns2_changed = new_config['nameserver2'] != config['nameserver2']
        dns3_changed = new_config['nameserver3'] != config['nameserver3']
        dnsservers_changed = any((dns1_changed, dns2_changed, dns3_changed))
        hostnames_changed = any((lhost_changed, bhost_changed, vhost_changed))

        if hostnames_changed or domainname_changed or dnssearch_changed or dnsservers_changed:
            await self.middleware.call('service.reload', 'resolvconf')
            await self.middleware.call('service.reload', 'nscd')

            # need to tell the CLI program to reload so it shows the new info
            def reload_cli():
                for process in psutil.process_iter(['pid', 'cmdline']):
                    cmdline = process.cmdline()
                    if len(cmdline) >= 2 and cmdline[1] == '/usr/bin/cli':
                        with contextlib.suppress(Exception):
                            process.send_signal(signal.SIGUSR1)

            await self.middleware.run_in_thread(reload_cli)

        # default gateway has changed
        if new_config['ipv4gateway'] != config['ipv4gateway'] or new_config['ipv6gateway'] != config['ipv6gateway']:
            await self.middleware.call('route.sync')

        # if virtual_hostname (only HA) or domain name changed
        # then restart nfs service if it's enabled and running
        # and we have a nfs principal in the keytab
        if vhost_changed or domainname_changed:
            if await self.middleware.call('kerberos.keytab.has_nfs_principal'):
                await self._service_change('nfs', 'restart')

        # proxy server has changed
        if new_config['httpproxy'] != config['httpproxy']:
            await self.middleware.call(
                'core.event_send',
                'network.config',
                'CHANGED',
                {'data': {'httpproxy': new_config['httpproxy']}}
            )

        # allowing outbound network activity has been changed
        if new_config['activity'] != config['activity']:
            await self.middleware.call('zettarepl.update_tasks')

        await self.middleware.call('network.configuration.toggle_announcement', new_config['service_announcement'])

        return await self.config()
