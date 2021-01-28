from pathlib import Path

from middlewared.schema import Dict, IPAddr, Int, Bool
from middlewared.service import (accepts, job, filterable,
                                 CRUDService, ValidationErrors)
from middlewared.utils import filter_list
from middlewared.plugins.cluster_linux.utils import CTDBConfig


PRI_LOCK = CTDBConfig.PRI_LOCK.value


class CtdbPrivateIpService(CRUDService):

    class Config:
        namespace = 'ctdb.private.ips'
        cli_private = True

    @filterable
    def query(self, filters, options):
        # logic is as follows:
        #   1. if ctdb daemon is started
        #       ctdb just reads the /etc private ip file and loads
        #       the ips written there into the cluster. However,
        #       if a private ip is added/removed, it doesn't
        #       mean the ctdb cluster has been reloaded to
        #       see the changes in the file. So return what
        #       the daemon sees.
        #   2. else
        #       if the ctdb shared volume  is mounted and /etc/ private
        #       ip file exists and is a symlink and the symlink is
        #       pointed to the /cluster private ip file then read it
        #       and return the contents
        ips = []
        if self.middleware.call_sync('service.started', 'ctdb'):
            ips = self.middleware.call_sync('ctdb.general.listnodes')
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
                pri_ip_file = Path(CTDBConfig.GM_PRI_IP_FILE.value)
                etc_ip_file = Path(CTDBConfig.ETC_PRI_IP_FILE.value)
                if pri_ip_file.exists():
                    if etc_ip_file.is_symlink() and etc_ip_file.resolve() == pri_ip_file:
                        with open(pri_ip_file) as f:
                            for idx, i in enumerate(f.read().splitlines()):
                                ips.append({
                                    'id': idx,
                                    'pnn': idx,
                                    'address': i.split('#')[1] if i.startswith('#') else i,
                                    'enabled': not i.startswith('#')
                                })

        return filter_list(ips, filters, options)

    @accepts(Dict(
        'private_create',
        IPAddr('ip'),
    ))
    @job(lock=PRI_LOCK)
    async def do_create(self, job, data):
        """
        Add a ctdb private address to the cluster

        `ip` string representing an IP v4/v6 address
        """

        schema_name = 'private_create'
        verrors = ValidationErrors()

        await self.middleware.call('ctdb.ips.common_validation', data, schema_name, verrors)
        await self.middleware.call('ctdb.ips.update_file', data, schema_name)

        return await self.middleware.call('ctdb.private.ips.query', [('address', '=', data['ip'])])

    @accepts(
        Int('id'),
        Dict(
            'private_update',
            Bool('enable', required=True)
        )
    )
    @job(lock=PRI_LOCK)
    async def do_update(self, job, id, option):
        """
        Update Private IP address from the ctdb cluster with pnn value of `id`.

        `id` integer representing the PNN value for the node.
        `enable` boolean. When True, enable the node else disable the node.
        """

        schema_name = 'private_update'
        verrors = ValidationErrors()

        data = await self.get_instance(id)
        data['enable'] = option['enable']

        await self.middleware.call('ctdb.ips.common_validation', data, schema_name, verrors)
        await self.middleware.call('ctdb.ips.update_file', data, schema_name)

        return await self.get_instance(id)
