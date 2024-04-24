import contextlib
import json
import os
import time

from middlewared.test.integration.utils import call, run_on_runner, RunOnRunnerException, IS_LINUX


@contextlib.contextmanager
def iscsi_auth(data):
    auth = call("iscsi.auth.create", data)

    try:
        yield auth
    finally:
        call("iscsi.auth.delete", auth["id"])


@contextlib.contextmanager
def iscsi_extent(data):
    extent = call("iscsi.extent.create", data)

    try:
        yield extent
    finally:
        call("iscsi.extent.delete", extent["id"])


@contextlib.contextmanager
def iscsi_host(data):
    host = call("iscsi.host.create", data)

    try:
        yield host
    finally:
        call("iscsi.host.delete", host["id"])


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


def target_login_test(portal_ip, target_name):
    if IS_LINUX:
        return target_login_test_linux(portal_ip, target_name)
    else:
        return target_login_test_freebsd(portal_ip, target_name)


def target_login_test_linux(portal_ip, target_name):
    try:
        if os.geteuid():
            # Non-root requires sudo
            iscsiadm = ['sudo', 'iscsiadm']
        else:
            iscsiadm = ['iscsiadm']
        run_on_runner(iscsiadm + ['-m', 'discovery', '-t', 'sendtargets', '--portal', portal_ip])
        run_on_runner(iscsiadm + ['-m', 'node', '--targetname', target_name, '--portal', portal_ip, '--login'])
    except RunOnRunnerException:
        return False
    else:
        run_on_runner(iscsiadm + ['-m', 'node', '--targetname', target_name, '--portal', portal_ip, '--logout'])
        return True


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


def target_login_impl_freebsd(portal_ip, target_name):
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


def target_login_test_freebsd(portal_ip, target_name):
    with iscsi_client_freebsd():
        try:
            target_login_impl_freebsd(portal_ip, target_name)
        except AssertionError:
            return False
        else:
            return True
        finally:
            run_on_runner(['iscsictl', '-R', '-t', target_name], check=False)
