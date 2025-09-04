from middlewared.service import private, Service

from .netif import netif


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    def lag_setup(self, lagg, members, parent_interfaces, sync_interface_opts):
        name = lagg['lagg_interface']['int_interface']
        self.logger.info('Setting up %s', name)

        try:
            iface = netif.get_interface(name)
        except KeyError:
            iface = None
        else:
            first_port = next(iter(iface.ports), None)
            if first_port is None or first_port[0] != members[0]['lagg_physnic']:
                self.logger.info('Destroying %s because its first port has changed', name)
                netif.destroy_interface(name)
                iface = None

        if iface is None:
            netif.create_interface(name)
            iface = netif.get_interface(name)

        info = {
            'protocol': None, 'xmit_hash_policy': None, 'lacpdu_rate': None, 'primary_interface': None, 'miimon': None,
        }
        protocol = getattr(netif.AggregationProtocol, lagg['lagg_protocol'].upper())
        if iface.protocol != protocol:
            info['protocol'] = protocol

        if protocol.name == 'FAILOVER':
            db_primary = [i['lagg_physnic'] for i in members][0]
            curr_primary = iface.primary_interface
            if curr_primary != db_primary:
                info['primary_interface'] = db_primary

        if iface.miimon == 0:
            info['miimon'] = 100

        if lagg['lagg_xmit_hash_policy']:
            # passing the xmit_hash_policy value needs to be lower-case
            # or `ip-link` will error with invalid argument
            xmit_hash = lagg['lagg_xmit_hash_policy'].lower()
            if iface.xmit_hash_policy != xmit_hash:
                info['xmit_hash_policy'] = xmit_hash

        # passing the lacp_rate value needs to be lower-case
        # or `ip-link` will error with invalid argument
        if lagg['lagg_lacpdu_rate']:
            lacpdu_rate = lagg['lagg_lacpdu_rate'].lower()
            if iface.lacpdu_rate != lacpdu_rate:
                info['lacpdu_rate'] = lacpdu_rate

        if any(i is not None for i in info.values()):
            # means one of the lagg options changed or is being
            # setup for the first time so we have to down the
            # interface before performing any of the actions
            iface.down()

            if info['protocol'] is not None:
                # we _always_ have to start with the protocol
                # information first since it deletes members
                # (if any) of the current lagg and then changes
                # the protocol
                self.logger.info('Changing protocol on %r to %s', name, info['protocol'].name)
                iface.protocol = info['protocol']

            if info['xmit_hash_policy'] is not None:
                self.logger.info('Changing xmit_hash_policy on %r to %s', name, info['xmit_hash_policy'])
                iface.xmit_hash_policy = info['xmit_hash_policy']

            if info['lacpdu_rate'] is not None:
                self.logger.info('Changing lacpdu_rate on %r to %s', name, info['lacpdu_rate'])
                iface.lacpdu_rate = info['lacpdu_rate']

            if info['primary_interface'] is not None:
                self.logger.info('Changing primary interface on %r to %s', name, info['primary_interface'])
                iface.primary_interface = info['primary_interface']

            if info['miimon'] is not None:
                try:
                    self.logger.info('Setting miimon on %r to %s ms', name, info['miimon'])
                    iface.miimon = info['miimon']
                except Exception:
                    self.logger.exception('Failed to set miimon on %r, interface may not support MII monitoring', name)

            # be sure and bring the lagg back up after making changes
            iface.up()

        members_database = []
        members_configured = {p[0] for p in iface.ports}
        for member in members:
            # For Link Aggregation MTU is configured in parent, not ports
            sync_interface_opts[member['lagg_physnic']]['skip_mtu'] = True
            members_database.append(member['lagg_physnic'])

        # Remove member ports configured in bond but do not exist in database
        iface.delete_ports(list(members_configured - set(members_database)))

        # Add member ports that exist in db but not configured in bond
        iface.add_ports([i for i in members_database if i not in members_configured])

        for port in iface.ports:
            try:
                port_iface = netif.get_interface(port[0])
            except KeyError:
                self.logger.warning('Could not find %s from %s', port[0], name)
                continue

            parent_interfaces.append(port[0])
            port_iface.up()
