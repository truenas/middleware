"""
Reproducer / regression test for the SCST "stale sysfs enable work vs target
unregistration" race, fixed by the scst core commit
"scst: Make target unregistration wait for queued enable/disable works".

Mechanism being exercised: writing a target's /sys/.../enabled attribute
queues a work item on the SCST sysfs work list and waits for it. The wait is
interruptible: if the writing process is killed, the write returns but the
work item STAYS QUEUED (holding a tgt kobject reference) and executes
whenever a sysfs thread gets to it -- possibly after scst_unregister_target()
has started tearing the target down. On unfixed kernels the stale work then
calls the target driver's enable_target() against a target whose driver side
is being (or has been) released -- a use-after-free of the driver's private
data. On an FC system this panicked in IRQ context (customer incident); with
iscsi-scst the corruption is usually silent on production kernels, so:

  - unfixed kernel: this test exercises the UAF window. It may pass silently;
    under a debug kernel (slub_debug=FZP or KASAN) it becomes reliably fatal.
  - fixed kernel: stale works are refused with a
    "Ignoring stale enable/disable of target ..." warning (counted and
    reported below), and nothing else happens.

The hard assertions are: no crash signatures in the kernel log delta, and
SCST target management still functional afterwards. The race is timing
dependent, so the churn is done in a single on-box shell loop (microsecond
interleavings, hundreds of iterations) rather than one ssh round trip per
step.
"""
import re
import time

import pytest
from assets.websocket.service import ensure_service_started

from middlewared.test.integration.utils import call, ssh

SERVICE_NAME = 'iscsitarget'
ISCSI_SYSFS = '/sys/kernel/scst_tgt/targets/iscsi'
TARGET_BASE = 'iqn.2005-10.org.freenas.ctl:stale-enable-test'

# ~30-50 ms per iteration on-box; 300 iterations ~= 10-15 s.
CHURN_ITERATIONS = 300
# Seconds the killed enable write is allowed to live. Small enough that a
# reasonable fraction of writes die before their work item has run.
WRITER_TTL = '0.02'

SERVICE_CYCLES = 4
STORM_TARGETS = 4
STORM_WRITERS_PER_TARGET = 4

CRASH_RE = re.compile(
    r'BUG:|Oops|general protection|kernel NULL pointer|refcount_t:|'
    r'list_del corruption|slab-use-after-free|Call Trace'
)
STALE_GUARD_RE = re.compile(r'Ignoring stale (enable|disable) of target')


@pytest.fixture(scope='module')
def iscsi_running():
    with ensure_service_started(SERVICE_NAME, 3):
        yield


def run_script(script):
    # Root's login shell on SCALE is zsh, which errors out on globs with no
    # matches; run the churn scripts under plain sh for POSIX semantics.
    ssh("sh <<'SCST_TEST_EOF'\n" + script + "\nSCST_TEST_EOF")


def kmsg_marker(tag):
    marker = f'SCST-STALE-ENABLE-TEST-{tag}-{time.time_ns()}'
    ssh(f"echo '{marker}' > /dev/kmsg")
    return marker


def dmesg_since(marker):
    return ssh(f"dmesg | sed -n '/{marker}/,$p'")


def assert_no_crash(log_delta):
    hits = [line for line in log_delta.splitlines() if CRASH_RE.search(line)]
    assert not hits, f'Kernel problem signatures during enable/unregister churn: {hits}'


def report_guard_count(log_delta, where):
    count = len(STALE_GUARD_RE.findall(log_delta))
    # Positive proof (fixed kernels only) that stale works were actually
    # injected and refused. Zero just means the timing dice missed or the
    # kernel predates the fix; not a failure either way.
    print(f'{where}: stale enable-work guard fired {count} time(s)')


def assert_scst_mgmt_functional():
    smoke = f'{TARGET_BASE}-smoke'
    ssh(f'echo "add_target {smoke}" > {ISCSI_SYSFS}/mgmt')
    assert smoke in ssh(f'ls {ISCSI_SYSFS}')
    ssh(f'echo "del_target {smoke}" > {ISCSI_SYSFS}/mgmt')


def test__stale_enable_work_vs_del_target(iscsi_running):
    """
    Tight on-box loop: create a target, start an "enabled" write and kill it
    after WRITER_TTL (leaving its work item queued some of the time), then
    immediately delete the target so unregistration races the queued work.
    """
    marker = kmsg_marker('churn')

    script = f'''
MGMT={ISCSI_SYSFS}/mgmt
i=0
while [ $i -lt {CHURN_ITERATIONS} ]; do
    tn={TARGET_BASE}$i
    if echo "add_target $tn" > $MGMT 2>/dev/null; then
        timeout -s KILL {WRITER_TTL} sh -c "echo 1 > {ISCSI_SYSFS}/$tn/enabled" 2>/dev/null &
        echo "del_target $tn" > $MGMT 2>/dev/null
        wait
    fi
    i=$((i+1))
done
for d in {ISCSI_SYSFS}/{TARGET_BASE}*; do
    if [ -d "$d" ]; then
        echo 0 > "$d/enabled" 2>/dev/null
        echo "del_target $(basename $d)" > $MGMT 2>/dev/null
    fi
done
true
'''
    run_script(script)

    log_delta = dmesg_since(marker)
    assert_no_crash(log_delta)
    report_guard_count(log_delta, 'del_target churn')
    assert_scst_mgmt_functional()


def test__enable_storm_vs_service_stop(iscsi_running):
    """
    Closest analog of the field incident: enable writes still in flight while
    the whole service (and with it every target, via scst_unregister_target)
    is being torn down. Writers are left running detached on the box, then the
    service is stopped out from under them.
    """
    marker = kmsg_marker('storm')

    for cycle in range(SERVICE_CYCLES):
        call('service.control', 'START', SERVICE_NAME, job=True)
        assert call('service.started', SERVICE_NAME) is True

        storm = f'''
MGMT={ISCSI_SYSFS}/mgmt
t=0
while [ $t -lt {STORM_TARGETS} ]; do
    echo "add_target {TARGET_BASE}-storm$t" > $MGMT 2>/dev/null
    w=0
    while [ $w -lt {STORM_WRITERS_PER_TARGET} ]; do
        nohup sh -c '
            n=0
            while [ $n -lt 100 ]; do
                timeout -s KILL {WRITER_TTL} sh -c "echo 1 > {ISCSI_SYSFS}/{TARGET_BASE}-storm'$t'/enabled" 2>/dev/null
                timeout -s KILL {WRITER_TTL} sh -c "echo 0 > {ISCSI_SYSFS}/{TARGET_BASE}-storm'$t'/enabled" 2>/dev/null
                n=$((n+1))
            done
        ' > /dev/null 2>&1 &
        w=$((w+1))
    done
    t=$((t+1))
done
true
'''
        run_script(storm)
        # Stop the service while the detached writers are still hammering the
        # enabled attributes; this unregisters every target underneath them.
        call('service.control', 'STOP', SERVICE_NAME, job=True)

    call('service.control', 'START', SERVICE_NAME, job=True)

    log_delta = dmesg_since(marker)
    assert_no_crash(log_delta)
    report_guard_count(log_delta, 'service-stop storm')
    assert_scst_mgmt_functional()
