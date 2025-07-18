import contextlib
import os
import sys
from time import monotonic, sleep

try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from auto_config import ha, hostname
except ImportError:
    ha = False
    hostname = None

from .call import call

__all__ = ["disable_failover", "do_failover"]


@contextlib.contextmanager
def disable_failover():
    if ha:
        call("failover.update", {"disabled": True, "master": True})

    try:
        yield
    finally:
        if ha:
            call("failover.update", {"disabled": False, "master": True})


def wait_for_standby():
    '''
    NOTE:
       1) This routine is for dual-controller (ha) only
       2) This is nearly identical to 'wait_for_standby' in test_006_pool_and_sysds

    This routine will wait for the standby controller to return from a reboot.
    '''
    if ha:
        sleep(5)

        sleep_time = 1
        max_wait_time = 300
        rebooted = False
        waited_time = 0

        while waited_time < max_wait_time and not rebooted:
            if call('failover.remote_connected'):
                rebooted = True
            else:
                waited_time += sleep_time
                sleep(sleep_time)

        assert rebooted, f'Standby did not connect after {max_wait_time} seconds'

        waited_time = 0  # need to reset this
        is_backup = False
        while waited_time < max_wait_time and not is_backup:
            try:
                is_backup = call('failover.call_remote', 'failover.status') == 'BACKUP'
            except Exception:
                pass

            if not is_backup:
                waited_time += sleep_time
                sleep(sleep_time)

        assert is_backup, f'Standby node did not become BACKUP after {max_wait_time} seconds'
        pass
    else:
        pass


def do_failover(delay=900, description=''):
    orig_master_node = call('failover.node')
    new_master = False
    failover_complete = False
    timeout = monotonic() + delay

    # First check that server is in expected failover state
    # This node is MASTER, remote is BACKUP, and no failover in progress
    assert call('failover.status') == 'MASTER'
    assert not call('failover.in_progress')
    assert call('failover.call_remote', 'failover.status') == 'BACKUP'

    call('system.reboot', f'do_failover(): {description}')

    while not new_master:
        try:
            new_master = call('failover.node') != orig_master_node
        except Exception:
            pass

        if not new_master:
            if monotonic() > timeout:
                break

            print("Waiting for backup")
            sleep(5)

    assert new_master, f'Did not switch to new controller after {delay} seconds.'

    # We have new controller, wait for standby to settle
    wait_for_standby()

    while not failover_complete:
        failover_complete = not call('failover.in_progress')
        if failover_complete:
            assert call('failover.status') == 'MASTER'
            assert call('failover.call_remote', 'failover.status') == 'BACKUP'

        else:
            if monotonic() > timeout:
                break

            print("Waiting for failover to complete")
            sleep(5)

    assert failover_complete, f'Did not complete failover after {delay} seconds.'
