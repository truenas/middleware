from pathlib import Path

from middlewared.schema import Dict, IPAddr, Int, Str, Bool
from middlewared.service import (accepts, job, filterable,
                                 CRUDService, ValidationErrors, private)
from middlewared.utils import filter_list, run
from middlewared.plugins.cluster_linux.utils import CTDBConfig
from middlewared.validators import IpAddress


PUB_LOCK = CTDBConfig.PUB_LOCK.value


class CtdbPublicIpService(CRUDService):

    class Config:
        namespace = 'ctdb.public.ips'
        cli_private = True

    @filterable
    def query(self, filters, options):
        normalized = []
        ctdb_ips = []
        if self.middleware.call_sync('service.started', 'ctdb'):
            ips = self.middleware.call_sync('ctdb.general.ips')
            ctdb_ips = list(map(lambda i: dict(i, id=i['public_ip'], enabled=(i['pnn'] >= 0)), ips))

        try:
            shared_vol = Path(CTDBConfig.CTDB_LOCAL_MOUNT.value)
            mounted = shared_vol.is_mount()
        except Exception:
            # can happen when mounted but glusterd service
            # is stopped/crashed etc
            mounted = False

        etc_ips = []
        if mounted:
            pub_ip_file = Path(CTDBConfig.GM_PUB_IP_FILE.value)
            etc_ip_file = Path(CTDBConfig.ETC_PUB_IP_FILE.value)
            if pub_ip_file.exists():
                if etc_ip_file.is_symlink() and etc_ip_file.resolve() == pub_ip_file:
                    with open(pub_ip_file) as f:
                        for idx, i in enumerate(f.read().splitlines()):
                            if not i.startswith('#'):
                                enabled = True
                                public_ip = i.split('/')[0]
                            else:
                                enabled = False
                                public_ip = i.split('#')[1].split('/')[0]

                            etc_ips.append({
                                'id': public_ip,
                                'pnn': -1 if not enabled else idx,
                                'enabled': enabled,
                                'public_ip': public_ip,
                                'interfaces': [{
                                    'name': i.split()[-1],
                                    'active': False,
                                    'available': False,
                                }]
                            })

        # if the public ip was gracefully disabled and ctdb daemon is running
        # then it will report the public ip address information, however,
        # if the ctdb daemon was restarted after it was disabled then it
        # won't report it at all, yet, it's still written to the config
        # file prepended with a "#". This is by design so we need to
        # make sure we normalize the output of what ctdb daemon reports
        # and what's been written to the public address config file
        normalized.extend(list(i for i in etc_ips if i not in ctdb_ips))

        return filter_list(normalized, filters, options)

    @private
    async def realloc(self):
        re = await run(['ctdb', 'ipreallocate'], encoding='utf8', errors='ignore', check=False)
        if re.returncode:
            # this isn't fatal it just means the newly added public ip won't show
            # up until the ctdb service has been restarted so just log a message
            self.logger.warning('Failed to gracefully reallocate public ip to running ctdb config: %r', re.stderr)

    @private
    async def update_running_config(self, data, disable=False):
        if not disable:
            ip = f'{data["ip"]}/{data["netmask"]} {data["interface"]}'
            add = await run(['ctdb', 'addip', ip], encoding='utf8', errors='ignore', check=False)
            if add.returncode:
                # this isn't fatal it just means the newly added public ip won't show
                # up until the ctdb service has been restarted so just log a message
                self.logger.warning('Failed to gracefully add public ip to running ctdb config: %r', add.stderr)
        else:
            rem = await run(['ctdb', 'delip', data['public_ip']], encoding='utf8', errors='ignore', check=False)
            if rem.returncode:
                # this isn't fatal it just means the public ip that was removed won't
                # go away until the ctdb service has been restarted so just log a message
                self.logger.warning('Failed to gracefully disable public ip in running ctdb config: %r', rem.stderr)

        # necessary for a removal or addition
        await self.middleware.call('ctdb.public.ips.realloc')

    @accepts(Dict(
        'public_create',
        IPAddr('ip', required=True),
        Int('netmask', required=True),
        Str('interface', required=True),
    ))
    @job(lock=PUB_LOCK)
    async def do_create(self, job, data):
        """
        Add a ctdb public address to the cluster

        `ip` string representing an IP v4/v6 address
        `netmask` integer representing a cidr notated netmask (i.e. 16/24/48/64 etc)
        `interface` string representing a network interface to apply the `ip`
        """

        schema_name = 'public_create'
        verrors = ValidationErrors()

        await self.middleware.call('ctdb.ips.common_validation', data, schema_name, verrors)
        await self.middleware.call('ctdb.ips.update_file', data, schema_name)

        if await self.middleware.call('service.started', 'ctdb'):
            # make sure the running config is updated
            await self.middleware.call('ctdb.public.ips.update_running_config', data)

        return await self.middleware.call('ctdb.public.ips.query', [('public_ip', '=', data['ip'])])

    @accepts(
        Str('ip', validators=[IpAddress()], required=True),
        Dict(
            'public_update',
            Bool('enable', required=True),
        )
    )
    @job(lock=PUB_LOCK)
    async def do_update(self, job, id, option):
        """
        Update Public IP address in the ctdb cluster.

        `ip` string representing the public ip address
        `enable` boolean. When True, enable the node else disable the node.
        """

        schema_name = 'public_update'
        verrors = ValidationErrors()

        data = await self.get_instance(id)
        data['enable'] = option['enable']

        await self.middleware.call('ctdb.ips.common_validation', data, schema_name, verrors)
        await self.middleware.call('ctdb.ips.update_file', data, schema_name)

        if await self.middleware.call('service.started', 'ctdb'):
            # make sure the running config is updated
            await self.middleware.call('ctdb.public.ips.update_running_config', data, True)

        return await self.get_instance(id)
