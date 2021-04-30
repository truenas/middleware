from middlewared.service import Service
from middlewared.utils import filter_list
from middlewared.plugins.interface.netif import netif


class DetectVirtualIpStates(Service):

    class Config:
        private = True
        namespace = 'failover.vip'

    async def check_failover_group(self, ifname, groups):

        """
        Check the other members (if any) in failover group for `ifname`
        """

        masters, backups = [], []

        # get failover group id for `iface`
        group_id = [
            group for group, names in groups.items() if ifname in names
        ][0]

        # get all interfaces in `group_id`
        ids = [
            names for group, names in groups.items() if group == group_id
        ][0]

        # need to remove the passed in `ifname` from the list
        ids.remove(ifname)

        # if the user provided VIP(s) is/are missing from the interface
        # then it's considered "BACKUP" if the interface has the VIP(s)
        # then it's considered "MASTER"
        if len(ids):

            # we can have more than one interface in the failover
            # group so check the state of the interface
            for i in ids:
                iface = netif.get_interface(i)
                for j in iface.vrrp_config:
                    if j['state'] == 'MASTER':
                        masters.append(i)
                    else:
                        backups.append(i)

        return masters, backups

    async def get_states(self, interfaces=None):

        """
        The `inits` list is not used on SCALE_ENTERPRISE but
        is kept here to provide backwards compatibility with
        ENTERPRISE API.
        """

        masters, backups, inits = [], [], []

        if interfaces is None:
            interfaces = await self.middleware.call('interface.query')

        int_ifaces = await self.middleware.call('failover.internal_interfaces')

        crit_ifaces = [
            i['id'] for i in filter_list(
                interfaces, [('failover_critical', '=', True)]
            )
        ]

        for iface in interfaces:
            if iface['name'] in int_ifaces:
                continue
            elif iface['name'] not in crit_ifaces:
                continue
            elif iface['state']['vrrp_config'][0]['state'] == 'MASTER':
                masters.append(iface['name'])
            elif iface['state']['vrrp_config'][0]['state'] == 'BACKUP':
                backups.append(iface['name'])
            else:
                self.logger.warning(
                    'Unknown VRRP state %s for interface %s',
                    iface['state']['vrrp_config'][0]['state'],
                    iface['name'],
                )

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
