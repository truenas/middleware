import time

from middlewared.test.integration.utils import call

__all__ = ['settle_ha']


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
                return
        except Exception:
            pass
        time.sleep(delay)
    raise ValueError(f'HA failed to settle: {reasons}')
