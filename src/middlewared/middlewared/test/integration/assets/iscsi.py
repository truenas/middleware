import contextlib

from middlewared.test.integration.utils import call, run_on_runner, RunOnRunnerException


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
    return target_login_test_generic(portal_ip, target_name)


def target_login_test_generic(portal_ip, target_name):
    try:
        run_on_runner(['iscsiadm', '-m', 'discovery', '-t', 'sendtargets', '--portal', portal_ip])
        run_on_runner(['iscsiadm', '-m', 'node', '--targetname', target_name, '--portal', portal_ip, '--login'])
    except RunOnRunnerException:
        return False
    else:
        run_on_runner(['iscsiadm', '-m', 'node', '--targetname', target_name, '--portal', portal_ip, '--logout'])
        return True
