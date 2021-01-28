from pathlib import Path

from middlewared.schema import Dict, IPAddr, Int, Str, Bool
from middlewared.service import (accepts, job, filterable,
                                 CRUDService, ValidationErrors)
from middlewared.utils import filter_list
from middlewared.plugins.cluster_linux.utils import CTDBConfig


PUB_LOCK = CTDBConfig.PUB_LOCK.value


class CtdbPublicIpService(CRUDService):

    class Config:
        namespace = 'ctdb.public.ips'
        cli_private = True

    @filterable
    def query(self, filters, options):
        # logic is as follows:
        #   1. if ctdb daemon is started
        #       ctdb just reads the /etc public ip file and loads
        #       the ips written there into the cluster. However,
        #       if a public ip is added/removed, it doesn't
        #       mean the ctdb cluster has been reloaded to
        #       see the changes in the file. So return what
        #       the daemon sees.
        #   2. if the ctdb shared volume is mounted and the /etc/ public
        #       ip file exists and is a symlink and the symlink is
        #       pointed to the /cluster public ip file then read it and
        #       return the contents
        ips = []
        if self.middleware.call_sync('service.started', 'ctdb'):
            ips = self.middleware.call_sync('ctdb.general.ips')
            ips = list(map(lambda i: dict(i, id=i['pnn']), ips))
        else:
            try:
                shared_vol = Path(CTDBConfig.CTDB_LOCAL_MOUNT.value)
                mounted = shared_vol.is_mount()
            except Exception:
                # can happen when mounted but glusterd service
                # is stopped/crashed etc
                mounted = False

            if mounted:
                pub_ip_file = Path(CTDBConfig.GM_PUB_IP_FILE.value)
                etc_ip_file = Path(CTDBConfig.ETC_PUB_IP_FILE.value)
                if pub_ip_file.exists():
                    if etc_ip_file.is_symlink() and etc_ip_file.resolve() == pub_ip_file:
                        with open(pub_ip_file) as f:
                            for idx, i in enumerate(f.read().splitlines()):
                                # we build a list of dicts that match what the
                                # ctdb daemon returns if it's running to keep
                                # things consistent
                                if not i.startswith('#'):
                                    enabled = True
                                    public_ip = i.split('/')[0]
                                else:
                                    enabled = False
                                    public_ip = i.split('#')[1]

                                ips.append({
                                    'id': idx,
                                    'pnn': idx,
                                    'enabled': enabled,
                                    'public_ip': public_ip,
                                    'interfaces': [{
                                        'name': i.split()[-1],
                                        'active': False,
                                        'available': False,
                                    }]
                                })

        return filter_list(ips, filters, options)

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

        return await self.middleware.call('ctdb.public.ips.query', [('public_ip', '=', data['ip'])])

    @accepts(
        Int('id'),
        Dict(
            'public_update',
            Bool('enable', required=True),
        )
    )
    @job(lock=PUB_LOCK)
    async def do_update(self, job, id, option):
        """
        Update Public IP address from the ctdb cluster with pnn value of `id`.

        `id` integer representing the PNN value of the node
        `enable` boolean. When True, enable the node else disable the node.
        """

        schema_name = 'public_update'
        verrors = ValidationErrors()

        data = await self.get_instance(id)
        data['enable'] = option['enable']

        await self.middleware.call('ctdb.ips.common_validation', data, schema_name, verrors)
        await self.middleware.call('ctdb.ips.update_file', data, schema_name)

        return await self.get_instance(id)
