from middlewared.schema import accepts, returns, List, Str
from middlewared.service import Service, throttle, pass_app, no_auth_required, private
from middlewared.plugins.failover_.utils import throttle_condition


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
    def get_reasons(self, app):
        reasons = set()

        fenced_running = self.middleware.call_sync('failover.fenced.run_info')['running']
        num_of_zpools_imported = len(self.middleware.call_sync('zfs.pool.query_imported_fast'))
        if fenced_running and num_of_zpools_imported <= 1:
            # returns the boot pool by default
            # fenced is running which implies it's the master node but we don't have any
            # zpools imported (or created)
            reasons.add('NO_VOLUME')
        elif not fenced_running and num_of_zpools_imported > 1:
            # zpool(s) imported but fenced isn't running which is bad
            reasons.add('NO_FENCED')

        if self.middleware.call_sync('failover.config')['disabled']:
            reasons.add('NO_FAILOVER')

        db = self.middleware.call_sync('datastore.query', 'network.interfaces')
        if not any((i['int_vip'] for i in db)):
            # only need 1 interface with a VIP
            reasons.add('NO_VIP')
        elif not any((i['int_critical'] for i in db)):
            # only need 1 interface marked critical for failover
            reasons.add('NO_CRITICAL_INTERFACES')

        try:
            assert self.middleware.call_sync('failover.remote_connected')

            # if the remote node panic's (this happens on failover event if we cant export the
            # zpool in 4 seconds on freeBSD systems (linux reboots silently by design)
            # then the p2p interface stays "UP" and the websocket remains open.
            # At this point, we have to wait for the TCP timeout (60 seconds default).
            # This means the assert line up above will return `True`.
            # However, any `call_remote` method will hang because the websocket is still
            # open but hasn't closed due to the default TCP timeout window. This can be painful
            # on failover events because it delays the process of restarting services in a timely
            # manner. To work around this, we place a `timeout` of 5 seconds on the system.ready
            # call. This essentially bypasses the TCP timeout window.
            if not self.middleware.call_sync('failover.call_remote', 'system.ready', [], {'timeout': 5}):
                reasons.add('NO_SYSTEM_READY')

            if not self.middleware.call_sync('failover.call_remote', 'failover.licensed'):
                reasons.add('NO_LICENSE')

            ifaces = self.middleware.call_sync('interface.query')
            local = self.middleware.call_sync('failover.vip.get_states', ifaces)
            remote = self.middleware.call_sync('failover.call_remote', 'failover.vip.get_states')
            if self.middleware.call_sync('failover.vip.check_states', local, remote):
                reasons.add('DISAGREE_VIP')

            mismatch_disks = self.middleware.call_sync('failover.mismatch_disks')
            if mismatch_disks['missing_local'] or mismatch_disks['missing_remote']:
                reasons.add('MISMATCH_DISKS')
        except Exception:
            reasons.add('NO_PONG')

        return reasons


async def setup(middleware):
    middleware.event_register('failover.disabled.reasons', 'Sent when failover status reasons change.')
