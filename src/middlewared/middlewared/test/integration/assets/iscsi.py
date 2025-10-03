import contextlib
import json
import os
import platform
import time
from pathlib import Path

from middlewared.test.integration.utils import call, run_on_runner, RunOnRunnerException

# We could be running these tests on a Linux or FreeBSD test-runner, so the commands
# used by a client can be different depending on the platform of the test runner
# (i.e. NOT related to CORE vs SCALE).
SYSTEM = platform.system().upper()
IS_LINUX = SYSTEM == "LINUX"


@contextlib.contextmanager
def iscsi_auth(data):
    auth = call("iscsi.auth.create", data)

    try:
        yield auth
    finally:
        call("iscsi.auth.delete", auth["id"])


@contextlib.contextmanager
def iscsi_extent(data, remove=False, force=False):
    extent = call("iscsi.extent.create", data)

    try:
        yield extent
    finally:
        call("iscsi.extent.delete", extent["id"], remove, force)


@contextlib.contextmanager
def iscsi_initiator(data):
    initiator = call("iscsi.initiator.create", data)

    try:
        yield initiator
    finally:
        call("iscsi.initiator.delete", initiator["id"])


@contextlib.contextmanager
def iscsi_portal(data):
    portal = call("iscsi.portal.create", data)

    try:
        yield portal
    finally:
        call("iscsi.portal.delete", portal["id"])


@contextlib.contextmanager
def iscsi_target(data):
    target = call("iscsi.target.create", data)

    try:
        yield target
    finally:
        call("iscsi.target.delete", target["id"])


def target_login_test(portal_ip, target_name, check_surfaced_luns=None):
    if IS_LINUX:
        return target_login_test_linux(portal_ip, target_name, check_surfaced_luns)
    else:
        return target_login_test_freebsd(portal_ip, target_name, check_surfaced_luns)


def target_login_test_linux(portal_ip, target_name, check_surfaced_luns=None):
    logged_in = False
    try:
        if os.geteuid():
            # Non-root requires sudo
            iscsiadm = ['sudo', 'iscsiadm']
        else:
            iscsiadm = ['iscsiadm']
        run_on_runner(iscsiadm + ['-m', 'discovery', '-t', 'sendtargets', '--portal', portal_ip])
        run_on_runner(iscsiadm + ['-m', 'node', '--targetname', target_name, '--portal', portal_ip, '--login'])
        logged_in = True
        if check_surfaced_luns is not None:
            retries = 20
            pattern = f'ip-{portal_ip}:3260-iscsi-{target_name}-lun-*'
            by_path = Path('/dev/disk/by-path')
            while retries:
                luns = set(int(p.name.split('-')[-1]) for p in by_path.glob(pattern))
                if luns == check_surfaced_luns:
                    break
                time.sleep(1)
                retries -= 1
            assert check_surfaced_luns == luns, luns
    except RunOnRunnerException:
        return False
    except AssertionError:
        return False
    else:
        return True
    finally:
        if logged_in:
            run_on_runner(iscsiadm + ['-m', 'node', '--targetname', target_name, '--portal', portal_ip, '--logout'])


@contextlib.contextmanager
def iscsi_client_freebsd():
    started = run_on_runner(['service', 'iscsid', 'onestatus'], check=False).returncode == 0
    if started:
        yield
    else:
        run_on_runner(['service', 'iscsid', 'onestart'])
        try:
            yield
        finally:
            run_on_runner(['service', 'iscsid', 'onestop'])


def target_login_impl_freebsd(portal_ip, target_name, check_surfaced_luns=None):
    run_on_runner(['iscsictl', '-A', '-p', portal_ip, '-t', target_name], check=False)
    retries = 5
    connected = False
    connected_clients = None
    # Unfortunately iscsictl can take some time to show the client as actually connected so adding a few retries here
    # to handle that case
    while retries > 0 and not connected:
        time.sleep(3)
        cp = run_on_runner(['iscsictl', '-L', '--libxo', 'json'])
        connected_clients = json.loads(cp.stdout)
        connected = any(
            session.get('state') == 'Connected' for session in connected_clients.get('iscsictl', {}).get('session', [])
            if session.get('name') == target_name
        )
        retries -= 1

    assert connected is True, connected_clients

    if check_surfaced_luns is not None:
        luns = set()
        for session in connected_clients.get('iscsictl', {}).get('session', []):
            if session.get('name') == target_name and session.get('state') == 'Connected':
                for lun in session.get('devices', {}).get('lun'):
                    if lun_val := lun.get('lun'):
                        luns.add(lun_val)
        assert check_surfaced_luns == luns, luns


def target_login_test_freebsd(portal_ip, target_name, check_surfaced_luns=None):
    with iscsi_client_freebsd():
        try:
            target_login_impl_freebsd(portal_ip, target_name, check_surfaced_luns)
        except AssertionError:
            return False
        else:
            return True
        finally:
            run_on_runner(['iscsictl', '-R', '-t', target_name], check=False)
