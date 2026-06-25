# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import logging
import os

logger = logging.getLogger('failover')


def stcnith_reboot(reason=None):
    """
    STCNITH (Shoot The Current Node In The Head): immediately and violently
    reboot THIS controller via the magic sysrq trigger, falling back to a
    `shutdown -r now` if sysrq is somehow unavailable.
    https://www.kernel.org/doc/html/latest/admin-guide/sysrq.html

    This is the only "safe" way to get the current node completely out of the
    way (e.g. on demotion) so that there is no chance of a zpool being imported
    on both nodes at once, which can ultimately end in data corruption.

    Idempotent: every step is best-effort and calling it more than once has the
    same end result (this node reboots ASAP). It performs NO failover validation
    so callers that require a guard (e.g. `failover.become_passive`) must do that
    check *before* calling.
    """
    if reason:
        logger.error('Force-rebooting this controller: %s', reason)
    try:
        # have to enable the "magic" sysrq triggers
        with open('/proc/sys/kernel/sysrq', 'w') as f:
            f.write('1')

        # now violently reboot
        with open('/proc/sysrq-trigger', 'w') as f:
            f.write('b')
    except Exception:
        # yeah...this isn't good
        logger.error('Unexpected failure triggering immediate reboot via sysrq', exc_info=True)
    finally:
        # this shouldn't be reached but better safe than sorry
        os.system('shutdown -r now')
