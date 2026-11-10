import time

from middlewared.test.integration.utils import call

__all__ = ['settle_ha', 'wait_ha_ready']


def settle_ha(delay=5, retries=24):
    """
    Wait for HA status to look settled.

    Default to 24 retries, with a 5 second delay => 2 minutes
    """
    reasons = []
    for i in range(retries):
        try:
            reasons = call('failover.disabled.reasons')
            if not reasons:
                assert not call('failover.call_remote', 'failover.in_progress')
                assert not call('failover.datastore.is_failure')
                return
        except Exception:
            pass
        time.sleep(delay)
    raise ValueError(f'HA failed to settle: {reasons}')


def wait_ha_ready(timeout=480, poll=5):
    """
    Wait until the HA pair is ready to fail over: no failover.disabled.reasons, the peer
    connected and BACKUP, and the database replicated to it.
    """
    deadline = time.monotonic() + timeout
    last = None
    while True:
        try:
            reasons = call('failover.disabled.reasons')
            connected = call('failover.remote_connected')
            peer = None
            if connected:
                peer = call('failover.call_remote', 'failover.status')
            # After a takeover, changes are not replicated until the new active controller
            # resends the database, retried every 30 s. Failing back earlier loses them.
            db_failure = call('failover.datastore.is_failure')
            last = {'reasons': reasons, 'connected': connected, 'peer': peer, 'db_failure': db_failure}
            if not reasons and connected and peer == 'BACKUP' and not db_failure:
                return
        except Exception as exc:
            # Transient while the peer reboots
            last = repr(exc)
        if time.monotonic() > deadline:
            raise TimeoutError(f'HA pair not ready after {timeout}s: {last}')
        time.sleep(poll)
