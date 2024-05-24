import ipaddress
import psutil
import contextlib
import signal

import middlewared.sqlalchemy as sa
from middlewared.service import ConfigService, private
from middlewared.schema import accepts, Patch, List, Dict, Int, Str, Bool, IPAddr, Ref, URI, ValidationErrors
from middlewared.validators import Match, Hostname

HOSTS_FILE_EARMARKER = '# STATIC ENTRIES'


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
    gc_hosts = sa.Column(sa.Text(), default='')
    gc_domains = sa.Column(sa.Text(), default='')
    gc_service_announcement = sa.Column(sa.JSON(dict), default={'mdns': True, 'wsdd': True, "netbios": False})
    gc_hostname_virtual = sa.Column(sa.String(120), nullable=True)
    gc_activity = sa.Column(sa.JSON(dict))


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
        URI('httpproxy', required=True),
        List('hosts', required=True, items=[Str('host')]),
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
    def read_etc_hosts_file(self):
        rv = []
        try:
            with open('/etc/hosts') as f:
                lines = f.read().splitlines()
        except FileNotFoundError:
            return rv

        try:
            start_pos = lines.index(HOSTS_FILE_EARMARKER) + 1
        except ValueError:
            # someone has manually modified file potentially
            return rv

        try:
            for idx in range(start_pos, len(lines)):
                if (entry := lines[idx].strip()):
                    rv.append(entry)
        except IndexError:
            # mako program should write file with an empty newline
            # but if someone manually removes it, make sure we dont
            # crash here
            return rv

        return rv

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
        if (hosts := data['hosts'].strip()):
            data['hosts'] = hosts.split('\n')
        else:
            data['hosts'] = []

        data['state'] = {
            'ipv4gateway': '',
            'ipv6gateway': '',
            'nameserver1': '',
            'nameserver2': '',
            'nameserver3': '',
            'hosts': self.read_etc_hosts_file(),
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
    async def validate_nameservers(self, verrors, data, schema):
        verrors = ValidationErrors()

        ns_ints = []
        for ns, ns_value in filter(lambda x: x[0].startswith('nameserver') and x[1], data.items()):
            schema = f'{schema}.{ns}'
            ns_ints.append(int(ns[-1]))
            try:
                nameserver_ip = ipaddress.ip_address(ns_value)
            except ValueError as e:
                verrors.add(schema, str(e))
            else:
                if nameserver_ip.is_loopback:
                    verrors.add(schema, 'Loopback is not a valid nameserver')
                elif nameserver_ip.is_unspecified:
                    verrors.add(schema, 'Unspecified addresses are not valid as nameservers')
                elif nameserver_ip.version == 4:
                    if ns_value == '255.255.255.255':
                        verrors.add(schema, 'This is not a valid nameserver address')
                    elif ns_value.startswith('169.254'):
                        verrors.add(schema, '169.254/16 subnet is not valid for nameserver')

        len_ns_ints = len(ns_ints)
        if len_ns_ints >= 2:
            ns_ints = sorted(ns_ints)
            for i in range(len_ns_ints - 1):
                if ns_ints[i - 1] - ns_ints[i] != 1:
                    verrors.add(
                        f'{schema}.nameserver{i}',
                        'When providing nameservers, they must be provided in consecutive order '
                        '(i.e. nameserver1, nameserver2, nameserver3)'
                    )

    @private
    async def validate_general_settings(self, data, schema):
        verrors = ValidationErrors()

        await self.validate_nameservers(verrors, data, schema)

        if (ipv4_gateway_value := data.get('ipv4gateway')):
            if not await self.middleware.call(
                'route.ipv4gw_reachable',
                ipaddress.ip_address(ipv4_gateway_value).exploded
            ):
                verrors.add(f'{schema}.ipv4gateway', f'Gateway {ipv4_gateway_value} is unreachable')

        if (domains := data.get('domains', [])) and len(domains) > 5:
            verrors.add(f'{schema}.domains', 'No more than 5 additional domains are allowed')

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
        if new_config == config:
            # nothing changed so return early
            return await self.config()

        verrors = await self.validate_general_settings(data, 'global_configuration_update')

        filters = [('timemachine', '=', True), ('enabled', '=', True)]
        if not new_config['service_announcement']['mdns'] and await self.middleware.call(
            'sharing.smb.query', filters, {'select': ['enabled', 'timemachine']}
        ):
            verrors.add(
                'global_configuration_update.service_announcement.mdns',
                'NAS is configured as a time machine target. mDNS is required.'
            )

        lhost_changed = rhost_changed = False
        this_node = await self.middleware.call('failover.node')
        if this_node in ('MANUAL', 'A'):
            lhost_changed = config['hostname'] != new_config['hostname']
            rhost_changed = config.get('hostname_b') and config['hostname_b'] != new_config['hostname_b']
        elif this_node == 'B':
            lhost_changed = config['hostname_b'] != new_config['hostname_b']
            rhost_changed = config['hostname'] != new_config['hostname']

        vhost_changed = config.get('hostname_virtual') and config['hostname_virtual'] != new_config['hostname_virtual']
        if vhost_changed and await self.middleware.call('directoryservices.summary'):
            verrors.add(
                'global_configuration_update.hostname_virtual',
                'This parameter may not be changed while bound to a directory service. '
                'If it must be changed, the proper procedure is to leave the domain '
                'and then alter the parameter before re-joining the domain.'
            )

        verrors.check()

        # pop the `hostname_local` key since that's created in the _extend method
        # and doesn't exist in the database
        new_config.pop('hostname_local', None)

        new_config['domains'] = ' '.join(new_config.get('domains', []))
        new_config['hosts'] = '\n'.join(new_config.get('hosts', []))

        # update the db
        await self.middleware.call(
            'datastore.update', 'network.globalconfiguration', config['id'], new_config, {'prefix': 'gc_'}
        )

        service_actions = set()
        if lhost_changed:
            await self.middleware.call('etc.generate', 'hostname')
            service_actions.add(('nscd', 'reload'))

        if rhost_changed:
            try:
                await self.middleware.call('failover.call_remote', 'etc.generate', ['hostname'])
            except Exception:
                self.logger.warning('Failed to set hostname on standby storage controller', exc_info=True)

        # dns domain name changed or /etc/hosts table changed
        licensed = await self.middleware.call('failover.licensed')
        domainname_changed = new_config['domain'] != config['domain']
        hosts_table_changed = new_config['hosts'] != config['hosts']
        if domainname_changed or hosts_table_changed:
            await self.middleware.call('etc.generate', 'hosts')
            service_actions.add(('nscd', 'reload'))
            if licensed:
                try:
                    await self.middleware.call('failover.call_remote', 'etc.generate', ['hosts'])
                except Exception:
                    self.logger.warning(
                        'Unexpected failure updating domain name and/or hosts table on standby controller',
                        exc_info=True
                    )

        # anything related to resolv.conf changed
        dnssearch_changed = new_config['domains'] != config['domains']
        dns1_changed = new_config['nameserver1'] != config['nameserver1']
        dns2_changed = new_config['nameserver2'] != config['nameserver2']
        dns3_changed = new_config['nameserver3'] != config['nameserver3']
        dnsservers_changed = any((dns1_changed, dns2_changed, dns3_changed))
        if dnssearch_changed or dnsservers_changed:
            await self.middleware.call('dns.sync')
            service_actions.add(('nscd', 'reload'))
            if licensed:
                try:
                    await self.middleware.call('failover.call_remote', 'dns.sync')
                except Exception:
                    self.logger.warning('Failed to generate resolv.conf on standby storage controller', exc_info=True)

            def reload_cli():
                for process in psutil.process_iter(['pid', 'cmdline']):
                    cmdline = process.cmdline()
                    if len(cmdline) >= 2 and cmdline[1] == '/usr/bin/cli':
                        with contextlib.suppress(Exception):
                            process.send_signal(signal.SIGUSR1)

            await self.middleware.run_in_thread(reload_cli)

        # default gateways changed
        ipv4gw_changed = new_config['ipv4gateway'] != config['ipv4gateway']
        ipv6gw_changed = new_config['ipv6gateway'] != config['ipv6gateway']
        if ipv4gw_changed or ipv6gw_changed:
            await self.middleware.call('route.sync')
            if licensed:
                try:
                    await self.middleware.call('failover.call_remote', 'route.sync')
                except Exception:
                    self.logger.warning('Failed to generate routes on standby storage controller', exc_info=True)

        # kerberized NFS needs to be restarted if these change
        if lhost_changed or vhost_changed or domainname_changed:
            if await self.middleware.call('kerberos.keytab.has_nfs_principal'):
                service_actions.add(('nfs', 'restart'))

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

        # handle the various service announcement daemons
        announce_changed = new_config['service_announcement'] != config['service_announcement']
        announce_srv = {'mdns': 'mdns', 'netbios': 'nmbd', 'wsd': 'wsdd'}
        if any((lhost_changed, vhost_changed)) or announce_changed:
            # lhost_changed is the local hostname and vhost_changed is the virtual hostname
            # and if either of these change then we need to toggle the service announcement
            # daemons irregardless whether or not these were toggled on their own
            for srv, enabled in new_config['service_announcement'].items():
                service_name = announce_srv[srv]
                started = await self.middleware.call('service.started', service_name)
                verb = None

                if enabled:
                    verb = 'restart' if started else 'start'
                else:
                    verb = 'stop' if started else None

                if not verb:
                    continue

                service_actions.add((service_name, verb))

        for service, verb in service_actions:
            await self.middleware.call(f'service.{verb}', service)

        await self.middleware.call('network.configuration.toggle_announcement', new_config['service_announcement'])

        return await self.config()
