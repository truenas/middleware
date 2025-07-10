import time

from middlewared.test.integration.utils import call

__all__ = ['settle_ha']


def settle_ha(delay=5, retries=24):
    reasons = []
    for i in range(retries):
        try:
            reasons = call('failover.disabled.reasons')
            if not reasons:
                return
        except Exception:
            pass
        time.sleep(delay)
    raise ValueError(f'HA failed to settle: {reasons}')
