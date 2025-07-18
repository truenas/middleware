import contextlib
import os
import sys
from time import sleep

try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from auto_config import ha as ha_enabled
except ImportError:
    ha_enabled = False

from .call import call
from .ha import settle_ha
from .ssh import ssh

__all__ = ["disable_failover", "do_failover"]


@contextlib.contextmanager
def disable_failover():
    if ha_enabled:
        call("failover.update", {"disabled": True, "master": True})

    try:
        yield
    finally:
        if ha:
            call("failover.update", {"disabled": False, "master": True})


def wait_for_standby(delay=5, retries=60):
    """ TODO: this is a wrapper around settle_ha, consumers should be fixed """
    if not ha_enabled:
        return

    settle_ha(delay, retries)


def do_failover(delay=5, settle_retries=180, description='', abusive=False):
    orig_master_node = call('failover.node')

    # This node is MASTER and failover isn't disabled for some reason
    assert call('failover.status') == 'MASTER'
    assert not call('failover.disabled.reasons')

    if abusive:
        ssh('echo 1 > /proc/sys/kernel/sysrq && echo b > /proc/sysrq-trigger', check=False)
    else:
        call('system.reboot', f'do_failover(): {description}')

    sleep(delay)
    settle_ha(delay, settle_retries)
    assert call('failover.node') != orig_master_node
