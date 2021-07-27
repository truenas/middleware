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
                        for i in f.read().splitlines():
                            if not i.startswith('#'):
                                enabled = True
                                public_ip = i.split('/')[0]
                            else:
                                enabled = False
                                public_ip = i.split('#')[1].split('/')[0]

                            etc_ips.append({
                                'id': public_ip,
                                'pnn': -1 if not enabled else 'N/A',
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
        normalized = []
        if not ctdb_ips:
            # means the ctdb daemon didn't return any type of
            # public address information so just return the
            # contents of etc_ips
            # NOTE: the contents of the etc file could be empty
            # (or not there) because it's a symlink pointed to
            # the cluster shared volume. In this case, there
            # isn't much we can do
            normalized = etc_ips
        else:
            if not etc_ips:
                # means the ctdb daemon is reporting public address(es)
                # however we're unable to read the config file which
                # could happen if the ctdb shared volume was umounted
                # while the ctdb daemon is running so we just return
                # what the daemon sees
                normalized = ctdb_ips
            else:
                # means the ctdb daemon is reporting public address(es)
                # and we have public addresses written to the config file
                # but it doesn't mean they necessarily match each other
                # so we need to normalize the output so the returned output
                # is always the same between the 2
                normalized.extend([i for i in ctdb_ips if i['public_ip'] not in [j.keys() for j in etc_ips]])

        return filter_list(normalized, filters, options)

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
        await self.middleware.call('ctdb.public.ips.reload')

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
        await self.middleware.call('ctdb.public.ips.reload')

        return await self.get_instance(id)
