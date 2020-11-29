from middlewared.service import Service


class DetectVirtualIpStates(Service):

    class Config:
        private = True
        namespace = 'failover.vip'

    async def get_states(self, interfaces=None):

        if interfaces is None:
            interfaces = await self.middleware.call('interface.query')

        masters, backups, inits = [], [], []

        internal_interfaces = await self.middleware.call(
            'failover.internal_interfaces'
        )

        critical_interfaces = [iface['int_interface']
                               for iface in await self.middleware.call('datastore.query', 'network.interfaces',
                                                                       [['int_critical', '=', True]])]

        for iface in interfaces:
            if iface['name'] in internal_interfaces:
                continue
            if iface['name'] not in critical_interfaces:
                continue
            if not iface['state']['carp_config']:
                continue
            if iface['state']['carp_config'][0]['state'] == 'MASTER':
                masters.append(iface['name'])
            elif iface['state']['carp_config'][0]['state'] == 'BACKUP':
                backups.append(iface['name'])
            elif iface['state']['carp_config'][0]['state'] in (None, 'INIT'):
                inits.append(iface['name'])
            else:
                self.logger.warning(
                    'Unknown CARP state %r for interface %s', iface['state']['carp_config'][0]['state'], iface['name']
                )

        return masters, backups, inits

    async def check_states(self, local, remote):

        errors = []

        interfaces = set(local[0] + local[1] + remote[0] + remote[1])
        if not interfaces:
            errors.append('There are no failover interfaces')

        for name in interfaces:
            if name not in local[0] + local[1]:
                errors.append(f'Interface {name} is not configured for failover on local system')
            if name not in remote[0] + remote[1]:
                errors.append(f'Interface {name} is not configured for failover on remote system')
            if name in local[0] and name in remote[0]:
                errors.append(f'Interface {name} is MASTER on both controllers.')
            if name in local[1] and name in remote[1]:
                errors.append(f'Interface {name} is BACKUP on both controllers.')

        for name in set(local[2] + remote[2]):
            if name not in local[2]:
                errors.append(f'Interface {name} is in a non-functioning state on local system.')
            if name not in remote[2]:
                errors.append(f'Interface {name} is in a non-functioning state on remote system.')

        return errors
