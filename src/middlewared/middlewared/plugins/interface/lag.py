from middlewared.service import private, Service

from .netif import netif


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    def lag_setup(self, lagg, members, disable_capabilities, parent_interfaces, sync_interface_opts):
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

        # FIXME: this will fail on SCALE since we don't even have
        # a "disable_capabilities" method
        """
        if disable_capabilities:
            self.middleware.call_sync('interface.disable_capabilities', name)
        """

        info = {'protocol': None, 'xmit_hash_policy': None, 'lacpdu_rate': None}
        protocol = getattr(netif.AggregationProtocol, lagg['lagg_protocol'].upper())
        if iface.protocol != protocol:
            info['protocol'] = protocol

        xmit_hash = lagg['lagg_xmit_hash_policy']
        if iface.xmit_hash_policy != xmit_hash:
            info['xmit_hash_policy'] = xmit_hash

        lacpdu_rate = lagg['lagg_lacpdu_rate']
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

            # be sure and bring the lagg back up after making changes
            iface.up()

        members_database = []
        members_configured = {p[0] for p in iface.ports}
        for member in members:
            # For Link Aggregation MTU is configured in parent, not ports
            sync_interface_opts[member['lagg_physnic']]['skip_mtu'] = True
            members_database.append(member['lagg_physnic'])

        # Remove member configured but not in database
        for member in (members_configured - set(members_database)):
            iface.delete_port(member)

        # Add member in database but not configured
        for member in members_database:
            if member in members_configured:
                continue

            iface.add_port(member)

        for port in iface.ports:
            try:
                port_iface = netif.get_interface(port[0])
            except KeyError:
                self.logger.warning('Could not find %s from %s', port[0], name)
                continue

            parent_interfaces.append(port[0])
            port_iface.up()
