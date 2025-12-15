#!/usr/bin/env python3
"""
Trigger immediate reboot on HA-capable systems when failover is enabled and system is licensed for failover.
This is the STCNITH method (Shoot The Current Node In The Head).
"""

import sys

from middlewared.plugins.failover_.detect_utils import detect_platform
from middlewared.plugins.failover_.ha_hardware import is_licensed_for_ha
from middlewared.utils.db import query_config_table


def is_ha_capable() -> bool:
    """Check if system is HA-capable hardware."""
    return detect_platform()[0] != 'MANUAL'


def is_failover_enabled() -> bool:
    """Check if failover is enabled (not administratively disabled)."""
    try:
        config = query_config_table('system_failover')
        return not config.get('disabled', False)
    except Exception:
        # If we can't read the config, assume failover is disabled
        return False


def trigger_panic() -> None:
    """Trigger immediate reboot via sysrq (same as failover.become_passive)."""
    # Enable sysrq triggers
    with open('/proc/sys/kernel/sysrq', 'w') as f:
        f.write('1')
    # Immediate reboot - no sync, no umount
    with open('/proc/sysrq-trigger', 'w') as f:
        f.write('b')


def main() -> int:
    if is_ha_capable() is False or is_failover_enabled() is False or is_licensed_for_ha() is False:
        # If system is not HA or if failover is explicitly disabled or if system is not licensed for HA, let's not panic
        return 0

    trigger_panic()
    return 0


if __name__ == '__main__':
    sys.exit(main())
