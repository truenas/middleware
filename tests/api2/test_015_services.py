import time
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call, ssh


@pytest.mark.flaky(reruns=5, reruns_delay=5)  # Sometimes systemd unit state is erroneously reported as active
def test_non_silent_service_start_failure():
    """
    This test for 2 conditions:
        1. middleware raises CallError that isn't empty
        2. each time a CallError is raised, the message
            has a timestamp and that timestamp changes
            with each failure
    """
    with pytest.raises(CallError) as e:
        call('service.start', 'ups', {'silent': False})

    # Error looks like
    """
    middlewared.service_exception.CallError: [EFAULT] Jan 10 08:49:14 systemd[1]: Starting Network UPS Tools - power device monitor and shutdown controller...
    Jan 10 08:49:14 nut-monitor[3032658]: fopen /run/nut/upsmon.pid: No such file or directory
    Jan 10 08:49:14 nut-monitor[3032658]: Unable to use old-style MONITOR line without a username
    Jan 10 08:49:14 nut-monitor[3032658]: Convert it and add a username to upsd.users - see the documentation
    Jan 10 08:49:14 nut-monitor[3032658]: Fatal error: unusable configuration
    Jan 10 08:49:14 nut-monitor[3032658]: Network UPS Tools upsmon 2.7.4
    Jan 10 08:49:14 systemd[1]: nut-monitor.service: Control process exited, code=exited, status=1/FAILURE
    Jan 10 08:49:14 systemd[1]: nut-monitor.service: Failed with result 'exit-code'.
    Jan 10 08:49:14 systemd[1]: Failed to start Network UPS Tools - power device monitor and shutdown controller.
    """
    lines1 = e.value.errmsg.splitlines()
    first_ts, len_lines1 = ' '.join(lines1.pop(0).split()[:3]), len(lines1)
    assert any('nut-monitor[' in line for line in lines1), lines1
    assert any('systemd[' in line for line in lines1), lines1

    # make sure we don't trigger system StartLimitBurst threshold
    # by removing this service from failed unit list (if it's there)
    ssh('systemctl reset-failed nut-monitor')

    # we have to sleep 1 second here or the timestamp will be the
    # same as when we first tried to start the service which is
    # what we're testing to make sure the message is up to date
    # with reality
    time.sleep(1)

    with pytest.raises(CallError) as e:
        call('service.start', 'ups', {'silent': False})

    # Error looks like: (Notice timestamp change, which is what we verify
    """
    middlewared.service_exception.CallError: [EFAULT] Jan 10 08:49:15 systemd[1]: Starting Network UPS Tools - power device monitor and shutdown controller...
    Jan 10 08:49:15 nut-monitor[3032739]: fopen /run/nut/upsmon.pid: No such file or directory
    Jan 10 08:49:15 nut-monitor[3032739]: Unable to use old-style MONITOR line without a username
    Jan 10 08:49:15 nut-monitor[3032739]: Convert it and add a username to upsd.users - see the documentation
    Jan 10 08:49:15 nut-monitor[3032739]: Fatal error: unusable configuration
    Jan 10 08:49:15 nut-monitor[3032739]: Network UPS Tools upsmon 2.7.4
    Jan 10 08:49:15 systemd[1]: nut-monitor.service: Control process exited, code=exited, status=1/FAILURE
    Jan 10 08:49:15 systemd[1]: nut-monitor.service: Failed with result 'exit-code'.
    Jan 10 08:49:15 systemd[1]: Failed to start Network UPS Tools - power device monitor and shutdown controller.
    """
    lines2 = e.value.errmsg.splitlines()
    second_ts, len_lines2 = ' '.join(lines2.pop(0).split()[:3]), len(lines2)
    assert any('nut-monitor[' in line for line in lines2), lines2
    assert any('systemd[' in line for line in lines2), lines2

    # timestamp should change since we sleep(1)
    assert first_ts != second_ts

    # the error messages will differ slightly (different PID for upsmon) but the number
    # of lines should be the same
    assert len_lines1 == len_lines2

    # Stop the service to avoid syslog spam
    call('service.stop', 'ups')
