from middlewared.schema import accepts, returns, List, Str
from middlewared.service import Service, throttle, pass_app, no_auth_required, private
from middlewared.plugins.failover_.utils import throttle_condition
from middlewared.service import CallError


class FailoverDisabledReasonsService(Service):

    class Config:
        cli_namespace = 'system.failover.disabled'
        namespace = 'failover.disabled'

    LAST_DISABLED_REASONS = None

    @no_auth_required
    @throttle(seconds=2, condition=throttle_condition)
    @accepts()
    @returns(List('reasons', items=[Str('reason')]))
    @pass_app()
    def reasons(self, app):
        """
        Returns a list of reasons why failover is not enabled/functional.

        NO_VOLUME - There are no pools configured.
        NO_VIP - There are no interfaces configured with Virtual IP.
        NO_SYSTEM_READY - Other storage controller has not finished booting.
        NO_PONG - Other storage controller is not communicable.
        NO_FAILOVER - Failover is administratively disabled.
        NO_LICENSE - Other storage controller has no license.
        DISAGREE_VIP - Nodes Virtual IP states do not agree.
        MISMATCH_DISKS - The storage controllers do not have the same quantity of disks.
        NO_CRITICAL_INTERFACES - No network interfaces are marked critical for failover.
        NO_FENCED - Zpools are imported but fenced isn't running.
        REM_FAILOVER_ONGOING - Other node is currently processing a failover event.
        NO_JOURNAL_SYNC - Thread responsible for syncing db transactions not running on this node.
        REM_NO_JOURNAL_SYNC - Thread responsible for syncing db transactions not running on other node.
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
    def get_local_reasons(self, app, ifaces, reasons):
        """This method checks the local node to try and determine its failover status."""
        if self.middleware.call_sync('failover.config')['disabled']:
            reasons.add('NO_FAILOVER')

        if not self.middleware.call_sync('failover.journal.thread_running'):
            reasons.add('NO_JOURNAL_SYNC')

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
            reasons.add('NO_CRITICAL_INTERFACES')
        elif not vip:
            reasons.add('NO_VIP')
        elif master:
            fenced_running = self.middleware.call_sync('failover.fenced.run_info')['running']
            num_of_zpools_imported = len(self.middleware.call_sync('zfs.pool.query_imported_fast'))
            if num_of_zpools_imported > 1:
                # boot pool is returned by default which is why we check > 1
                if not fenced_running:
                    # zpool(s) imported but fenced isn't running which is bad
                    reasons.add('NO_FENCED')
            else:
                # we've got interfaces marked as master but we have no zpool(s) imported
                reasons.add('NO_VOLUME')

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
                reasons.add('NO_SYSTEM_READY')

            if not self.middleware.call_sync('failover.call_remote', 'failover.licensed'):
                reasons.add('NO_LICENSE')

            args = [
                [["method", "in", ["failover.events.vrrp_master", "failover.events.vrrp_backup"]]],
                {"order_by": ["-id"]}
            ]
            if rv := self.middleware.call_sync('failover.call_remote', 'core.get_jobs', args):
                if rv[0]['state'] == 'RUNNING':
                    reasons.add('REM_FAILOVER_ONGOING')

            try:
                rv = self.middleware.call_sync('failover.call_remote', 'failover.journal.thread_running')
                if not rv:
                    reasons.add('REM_NO_JOURNAL_SYNC')
            except CallError as e:
                if e.errno == CallError.ENOMETHOD:
                    # the other node is running an old version so it'll fail as expected
                    # just ignore this error since the other node will eventually be updated
                    # to the same version as the current node
                    pass
                else:
                    raise

            local = self.middleware.call_sync('failover.vip.get_states', ifaces)
            remote = self.middleware.call_sync('failover.call_remote', 'failover.vip.get_states')
            if self.middleware.call_sync('failover.vip.check_states', local, remote):
                reasons.add('DISAGREE_VIP')

            mismatch_disks = self.middleware.call_sync('failover.mismatch_disks')
            if mismatch_disks['missing_local'] or mismatch_disks['missing_remote']:
                reasons.add('MISMATCH_DISKS')
        except Exception:
            reasons.add('NO_PONG')

    @private
    def get_reasons(self, app):
        reasons = set()
        ifaces = self.middleware.call_sync('interface.query')
        self.get_local_reasons(app, ifaces, reasons)
        self.get_remote_reasons(app, ifaces, reasons)

        return reasons


async def setup(middleware):
    middleware.event_register('failover.disabled.reasons', 'Sent when failover status reasons change.',
                              no_auth_required=True)
