import errno
import contextlib
from pathlib import Path

from middlewared.schema import Dict, IPAddr, Int, Str, Bool, List, returns
from middlewared.service import (accepts, job, filterable,
                                 CRUDService, ValidationErrors, private)
from middlewared.utils import filter_list, run
from middlewared.plugins.cluster_linux.utils import CTDBConfig
from middlewared.validators import IpAddress
from middlewared.service_exception import CallError


PUB_LOCK = CTDBConfig.PUB_LOCK.value


class CtdbPublicIpService(CRUDService):

    class Config:
        namespace = 'ctdb.public.ips'
        cli_namespace = 'service.ctdb.public.ips'

    @accepts(List('exclude_ifaces', items=[Str('exclude_iface')], default=[]))
    @returns(List(items=[Str('interface')]))
    async def interface_choices(self, exclude):
        """
        Retrieve list of available interface choices that can be used for assigning a ctdbd public ip.
        """
        priv_ips = {i['address'] for i in (await self.middleware.call('ctdb.private.ips.query'))}
        if not priv_ips:
            raise CallError('No ctdbd private IP addresses were detected', errno.ENOENT)

        filters = [['type', 'nin', ['BRIDGE']]]
        options = {'select': ['id', 'aliases']}
        ifaces = await self.middleware.call('interface.query', filters, options)
        if exclude and (bad := set(exclude) - set([i['id'] for i in ifaces])):
            raise CallError(f'Invalid exclude interface(s) {", ".join(bad)}', errno.ENOENT)

        choices = set()
        for i in ifaces:
            for j in filter(lambda x: x['type'] != 'LINK' and x['address'] not in priv_ips, i['aliases']):
                choices.add(i['id'])

        return sorted(choices - set(exclude))

    @filterable
    def query(self, filters, options):
        """
        Retrieve information about configured public IP addresses for the
        ctdb cluster. This call raise a CallError with errno set to ENXIO
        if this node is not in a state where it can provide accurate
        information about cluster. Examples problematic states are:

        - ctdb or glusterd are not running on this node

        - ctdb shared volume is not mounted
        """
        if not self.middleware.call_sync('service.started', 'ctdb'):
            raise CallError(
                "ctdb is not running. Unable to gather public address info",
                errno.ENXIO
            )

        ctdb_ips = self.middleware.call_sync('ctdb.general.ips')

        try:
            shared_vol = Path(CTDBConfig.CTDB_LOCAL_MOUNT.value)
            mounted = shared_vol.is_mount()
        except Exception:
            # can happen when mounted but glusterd service
            # is stopped/crashed etc
            mounted = False

        if not mounted:
            raise CallError("CTDB shared volume is in unhealthy state.", errno.ENXIO)

        nodes = {}

        for entry in self.middleware.call_sync('ctdb.general.listnodes'):
            """
            Skip disabled nodes since they cannot hold public addresses.
            If a node does not have a public_addresses file, we should still
            return an entry for it (but without any configured_addresses).
            This allows us to accurately report cases where perhaps due to
            user intervention, public address file was removed but ctdb
            IPs have not been reloaded.
            """
            if not entry['enabled']:
                continue

            pnn = entry['pnn']
            nodes[pnn] = {
                'id': pnn,
                'pnn': pnn,
                'configured_ips': {},
                'active_ips': {}
            }

            with contextlib.suppress(FileNotFoundError):
                with open(f'{shared_vol}/public_addresses_{pnn}') as f:
                    for i in f.read().splitlines():
                        if not i.startswith('#'):
                            enabled = True
                            public_ip = i.split('/')[0]
                        else:
                            enabled = False
                            public_ip = i.split('#')[1].split('/')[0]

                        nodes[pnn]['configured_ips'].update({
                            public_ip: {
                                'enabled': enabled,
                                'public_ip': public_ip,
                                'interface_name': i.split()[-1]
                            }
                        })

        for entry in ctdb_ips:
            if not nodes.get(entry['pnn']):
                """
                Most likely case here is that we're transitioning IP and it's
                current pnn is -1. Generate log message for now, and we can
                determine in future whether more action is required.
                """
                self.logger.warning(
                    "%s: active ip address does not exist in public_addresses file",
                    entry['public_ip']
                )
                continue

            nodes[entry['pnn']]['active_ips'].update({
                entry['public_ip']: entry['interfaces']
            })

        return filter_list(list(nodes.values()), filters, options)

    @private
    async def reload(self):
        """
        Reload the public addresses configuration file on the ctdb nodes. When it completes
        the public addresses will be reconfigured and reassigned across the cluster as
        necessary.
        """
        if await self.middleware.call('service.started', 'ctdb'):
            re = await run(['ctdb', 'reloadips'], encoding='utf8', errors='ignore', check=False)
            if re.returncode:
                # this isn't fatal it just means the newly added public ip won't show
                # up until the ctdb service has been restarted so just log a message
                self.logger.warning('Failed to reload public ip addresses %r', re.stderr)

    @accepts(Dict(
        'public_create',
        Int('pnn', required=True),
        IPAddr('ip', required=True),
        Int('netmask', required=True),
        Str('interface', required=True),
    ))
    @job(lock=PUB_LOCK)
    async def do_create(self, job, data):
        """
        Add a ctdb public address to the cluster

        `pnn` node number of record to adjust
        `ip` string representing an IP v4/v6 address
        `netmask` integer representing a cidr notated netmask (i.e. 16/24/48/64 etc)
        `interface` string representing a network interface to apply the `ip`
        """

        schema_name = 'public_create'
        verrors = ValidationErrors()

        await self.middleware.call('ctdb.ips.common_validation', data, schema_name, verrors)
        await self.middleware.call('ctdb.ips.update_file', data, schema_name)
        await self.middleware.call('ctdb.public.ips.reload')

        return await self.middleware.call('ctdb.public.ips.query', [('id', '=', data['pnn'])])

    @accepts(
        Int('pnn', required=True),
        Dict(
            'public_update',
            Str('ip', validators=[IpAddress()], required=True),
            Bool('enable', required=True),
        )
    )
    @job(lock=PUB_LOCK)
    async def do_update(self, job, id, option):
        """
        Update Public IP address in the ctdb cluster.
        `pnn` - cluster node number
        `ip` string representing the public ip address
        `enable` boolean. When True, enable the node else disable the node.
        """

        schema_name = 'public_update'
        verrors = ValidationErrors()

        data = await self.get_instance(id)
        data['enable'] = option['enable']

        await self.middleware.call('ctdb.ips.common_validation', data, schema_name, verrors)
        await self.middleware.call('ctdb.ips.update_file', data, schema_name)
        await self.middleware.call('ctdb.public.ips.reload')

        return await self.get_instance(id)
