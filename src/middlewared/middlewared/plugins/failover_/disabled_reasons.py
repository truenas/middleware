# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions
from enum import Enum

from middlewared.schema import accepts, returns, List, Str
from middlewared.service import Service, CallError, pass_app, no_auth_required, private
from middlewared.plugins.interface.netif import netif
from middlewared.utils.zfs import query_imported_fast_impl


class DisabledReasonsEnum(str, Enum):
    NO_CRITICAL_INTERFACES = 'No network interfaces are marked critical for failover.'
    MISMATCH_DISKS = 'The quantity of disks do not match between the nodes.'
    MISMATCH_VERSIONS = 'TrueNAS software versions do not match between storage controllers.'
    MISMATCH_NICS = 'NIC hardware does not match between nodes.'
    DISAGREE_VIP = 'Nodes Virtual IP states do not agree.'
    NO_LICENSE = 'Other node has no license.'
    NO_FAILOVER = 'Administratively Disabled.'
    NO_PONG = 'Unable to contact remote node via the heartbeat interface.'
    NO_VOLUME = 'No zpools have been configured.'
    NO_VIP = 'No interfaces have been configured with a Virtual IP.'
    NO_SYSTEM_READY = 'Other node has not finished booting.'
    NO_FENCED = 'Fenced is not running.'
    REM_FAILOVER_ONGOING = 'Other node is currently processing a failover event.'
    LOC_FAILOVER_ONGOING = 'This node is currently processing a failover event.'
    NO_HEARTBEAT_IFACE = 'Local heartbeat interface does not exist.'
    NO_CARRIER_ON_HEARTBEAT = 'Local heartbeat interface is down.'
    LOC_FIPS_REBOOT_REQ = 'This node needs to be rebooted to apply FIPS configuration'
    REM_FIPS_REBOOT_REQ = 'Other node needs to be rebooted to apply FIPS configuration'


class FailoverDisabledReasonsService(Service):

    class Config:
        cli_namespace = 'system.failover.disabled'
        namespace = 'failover.disabled'

    LAST_DISABLED_REASONS = None

    @no_auth_required
    @accepts()
    @returns(List('reasons', items=[Str('reason')]))
    @pass_app()
    def reasons(self, app):
        """Returns a list of reasons why failover is not enabled/functional.
        See `DisabledReasonsEnum` for the reasons and their explanation.
        """
        reasons = self.middleware.call_sync('failover.disabled.get_reasons', app)
        if reasons != FailoverDisabledReasonsService.LAST_DISABLED_REASONS:
            FailoverDisabledReasonsService.LAST_DISABLED_REASONS = reasons
            self.middleware.send_event(
                'failover.disabled.reasons', 'CHANGED',
                fields={'disabled_reasons': list(reasons)}
            )
        return list(reasons)

    @private
    def heartbeat_health(self, app, reasons):
        try:
            heartbeat_iface_name = self.middleware.call_sync('failover.internal_interface.detect')[0]
        except IndexError:
            # if something calls this directly from cli on a non-ha machine, don't
            # crash since it's easily avoided
            return

        try:
            iface = netif.list_interfaces()[heartbeat_iface_name]
            if iface.link_state != 'LINK_STATE_UP':
                reasons.add(DisabledReasonsEnum.NO_CARRIER_ON_HEARTBEAT.name)
        except KeyError:
            # saw this on an internal m50 because the systemd-modules-load.service
            # timed out and was subsequently killed so the ntb kernel module didn't
            # get loaded
            reasons.add(DisabledReasonsEnum.NO_HEARTBEAT_IFACE.name)

    @private
    def get_local_reasons(self, app, ifaces, reasons):
        """This method checks the local node to try and determine its failover status."""
        if self.middleware.call_sync('failover.config')['disabled']:
            reasons.add(DisabledReasonsEnum.NO_FAILOVER.name)

        if self.middleware.call_sync('failover.in_progress'):
            reasons.add(DisabledReasonsEnum.LOC_FAILOVER_ONGOING.name)
            # no reason to check anything else since failover
            # is happening on this system
            return

        reboot_info = self.middleware.call_sync('failover.reboot.info')
        if reboot_info['this_node']['reboot_required']:
            reasons.add(DisabledReasonsEnum.LOC_FIPS_REBOOT_REQ.name)
        if reboot_info['other_node']['reboot_required']:
            reasons.add(DisabledReasonsEnum.REM_FIPS_REBOOT_REQ.name)

        self.heartbeat_health(app, reasons)

        crit_iface = vip = master = False
        for iface in ifaces:
            if iface['failover_critical']:
                # only need 1 interface marked critical for failover
                crit_iface = True

            if iface['failover_virtual_aliases']:
                # only need 1 interface with a virtual IP
                vip = True

            if any((i['state'] == 'MASTER' for i in iface['state'].get('vrrp_config') or [])):
                # means this interface is MASTER
                master = True

        if not crit_iface:
            reasons.add(DisabledReasonsEnum.NO_CRITICAL_INTERFACES.name)
        elif not vip:
            reasons.add(DisabledReasonsEnum.NO_VIP.name)
        elif master:
            fenced_running = self.middleware.call_sync('failover.fenced.run_info')['running']
            num_of_zpools_imported = len(query_imported_fast_impl())
            if num_of_zpools_imported > 1:
                # boot pool is returned by default which is why we check > 1
                if not fenced_running:
                    # zpool(s) imported but fenced isn't running which is bad
                    reasons.add(DisabledReasonsEnum.NO_FENCED.name)
            else:
                # we've got interfaces marked as master but we have no zpool(s) imported
                reasons.add(DisabledReasonsEnum.NO_VOLUME.name)

    @private
    def get_remote_reasons(self, app, ifaces, reasons):
        """This method checks the remote node to try and determine its failover status."""
        try:
            assert self.middleware.call_sync('failover.remote_connected')
            if not self.middleware.call_sync('failover.call_remote', 'system.ready', [], {'timeout': 5}):
                # if the remote node panic's (this happens on failover event if we cant export the
                # zpool in 4 seconds (linux reboots silently by design) then the p2p interface stays
                # "UP" and the websocket remains open. At this point, we have to wait for the TCP
                # timeout (60 seconds default). This means the assert line up above will return `True`.
                # However, any `call_remote` method will hang because the websocket is still
                # open but hasn't closed due to the default TCP timeout window. This can be painful
                # on failover events because it delays the process of restarting services in a timely
                # manner. To work around this, we place a `timeout` of 5 seconds on the system.ready
                # call. This essentially bypasses the TCP timeout window.
                reasons.add(DisabledReasonsEnum.NO_SYSTEM_READY.name)

            if not self.middleware.call_sync('failover.call_remote', 'failover.licensed'):
                reasons.add(DisabledReasonsEnum.NO_LICENSE.name)

            lsw = self.middleware.call_sync('system.version')
            rsw = self.middleware.call_sync('failover.call_remote', 'system.version')
            if lsw != rsw:
                reasons.add(DisabledReasonsEnum.MISMATCH_VERSIONS.name)

            if self.middleware.call_sync('failover.call_remote', 'failover.in_progress'):
                reasons.add(DisabledReasonsEnum.REM_FAILOVER_ONGOING.name)

            local = self.middleware.call_sync('failover.vip.get_states', ifaces)
            remote = self.middleware.call_sync('failover.call_remote', 'failover.vip.get_states')
            if self.middleware.call_sync('failover.vip.check_states', local, remote):
                reasons.add(DisabledReasonsEnum.DISAGREE_VIP.name)

            mismatch_disks = self.middleware.call_sync('failover.mismatch_disks')
            if mismatch_disks['missing_local'] or mismatch_disks['missing_remote']:
                reasons.add(DisabledReasonsEnum.MISMATCH_DISKS.name)

            if self.middleware.call_sync('failover.mismatch_nics'):
                reasons.add(DisabledReasonsEnum.MISMATCH_NICS.name)
        except Exception:
            reasons.add(DisabledReasonsEnum.NO_PONG.name)

    @private
    def get_reasons(self, app):
        reasons = set()
        if self.middleware.call_sync('failover.licensed'):
            ifaces = self.middleware.call_sync('interface.query')
            self.get_local_reasons(app, ifaces, reasons)
            self.get_remote_reasons(app, ifaces, reasons)

        return reasons


async def setup(middleware):
    middleware.event_register('failover.disabled.reasons', 'Sent when failover status reasons change.',
                              no_auth_required=True)
