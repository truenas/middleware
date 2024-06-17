# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.service import Service


class DetectVirtualIpStates(Service):

    class Config:
        private = True
        namespace = 'failover.vip'

    async def check_failover_group(self, ifname, groups):
        """
        Check the other members (if any) in failover group for `ifname`
        """
        failover_grp_ifaces = list()
        for grp, names in groups.items():
            if ifname in names:
                # get the list of interfaces that are in the same
                # failover group as `ifname`.
                failover_grp_ifaces = names[:]

                # we remove `ifname` since we only care about the other
                # interfaces in this failover group
                failover_grp_ifaces.remove(ifname)

                # An interface can only ever be in a single failover
                # group so we can break the loop early here
                break

        masters, backups, offline = list(), list(), list()
        filters = [['id', 'in', failover_grp_ifaces]]
        for i in await self.middleware.call('interface.query', filters):
            if i['state'].get('link_state') != 'LINK_STATE_UP':
                # It's not common, but some users will configure interfaces
                # for failover but they won't be online. In this scenario
                # the interfaces will appear as "backup", but that's
                # misleading since they technically are backup they're not
                # actually participating in any VRRP negotiations. In this
                # instance, we'll mark them as offline
                offline.append(i['id'])
                continue

            # We're checking any other interface that is in the same
            # failover group as `ifname`. For example, customers often
            # configure multiple physical interfaces for iSCSI MPIO.
            # Since they are using MPIO, each interface serves as a
            # discreet path to their data. However, if 1 of the 4
            # interfaces go down then we don't need to failover since
            # 3 other paths are up (That's the point of MPIO). In this
            # scenario, the customer will have to put all 4 of the
            # physical interfaces in the _same_ failover group.
            for vrrp_info in (i['state'].get('vrrp_config') or []):
                # `vrrp_config` can be NoneType when a bond interface
                # has been configured that has no config on it. The
                # reason why a bond will have no config is when it's
                # used as a parent interface to host vlan interfaces.
                # In this scenario, vrrp_config is expected to be None.
                if vrrp_info['state'] == 'MASTER':
                    masters.append(i['id'])
                else:
                    backups.append(i['id'])

        return masters, backups, offline

    async def get_states(self, interfaces=None):
        masters, backups, inits = [], [], []

        if interfaces is None:
            interfaces = await self.middleware.call('interface.query')

        int_ifaces = await self.middleware.call('interface.internal_interfaces')
        for i in filter(lambda x: x['name'] not in int_ifaces and x['state']['vrrp_config'], interfaces):
            if i['state']['link_state'] == 'LINK_STATE_UP':
                vrrp_state = i['state']['vrrp_config'][0]['state']
                if vrrp_state == 'MASTER':
                    masters.append(i['name'])
                elif vrrp_state == 'BACKUP':
                    backups.append(i['name'])

        return masters, backups, inits

    async def check_states(self, local, remote):
        errors = []
        interfaces = set(local[0] + local[1] + remote[0] + remote[1])
        if not interfaces:
            errors.append('There are no failover interfaces')

        for name in interfaces:
            if name in local[1] and name in remote[1]:
                errors.append(f'Interface "{name}" is BACKUP on both nodes')
            if name in local[0] and name in remote[0]:
                errors.append(f'Interface "{name}" is MASTER on both nodes')

        return errors
