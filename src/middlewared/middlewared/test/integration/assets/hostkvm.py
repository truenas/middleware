import json
import os
import re
import shlex

from middlewared.test.integration.utils import RunOnRunnerException, call, run_on_runner, ssh
from middlewared.test.integration.utils.client import client as tn_client

try:
    from config import KVM_HOST, KVM_PASSWORD, KVM_USERNAME
    have_kvm_host_cfg = True
except ImportError:
    have_kvm_host_cfg = False

TN_TEST_CONFIG_PATH = '/etc/tn-test/config.json'

TM_NODE_RE = re.compile('^tm[0-9]{3}$')
HA_NODE_RE = re.compile('^ha[0-9]{3}_c[1|2]$')
WHOLE_HA_NODE_RE = re.compile('^ha[0-9]{3}$')


def _tn_test_config():
    """
    Return the parsed /etc/tn-test/config.json if present, else None.
    Its presence indicates the test runner is talking to guest VMs hosted
    on a TrueNAS box (via the TrueNAS vm APIs) rather than a Debian/KVM host.
    """
    try:
        with open(TN_TEST_CONFIG_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def _tn_client(cfg):
    return tn_client(host_ip=cfg['tn_host'], auth=(cfg['tn_username'], cfg['tn_password']))


def _tn_vm_id(c, vmname):
    vms = c.call('vm.query', [['name', '=', vmname]])
    if not vms:
        raise RuntimeError(f'{vmname}: VM not found on TrueNAS host')
    return vms[0]['id']


def get_kvm_domain():
    """Fetch the name of the KVM domain."""
    # By convention we have written it into DMI system serial number
    info = call('system.dmidecode_info')
    if serial := info.get('system-serial-number'):
        # Verify that the string looks reasonable
        if TM_NODE_RE.match(serial) or HA_NODE_RE.match(serial):
            return serial


def _virsh(command):
    """
    Execute the virsh command sequence.
    """
    if have_kvm_host_cfg:
        virsh = ['sudo', 'virsh']
        ssh_command = shlex.join(virsh + command)
        return ssh(ssh_command, user=KVM_USERNAME, password=KVM_PASSWORD, ip=KVM_HOST)
    else:
        try:
            if os.geteuid():
                # Non-root requires sudo
                virsh = ['sudo', 'virsh']
            else:
                virsh = ['virsh']
            cp = run_on_runner(virsh + command)
        except RunOnRunnerException:
            raise
        except AssertionError:
            raise
        else:
            return cp.stdout


def poweroff_vm(vmname, graceful=True):
    """
    Issue a virsh destroy <domain>.  This is similar to pulling the power
    cable.  The VM can be restarted later.
    """
    if cfg := _tn_test_config():
        # virsh destroy [--graceful] is a hard poweroff of qemu; the guest
        # never sees ACPI.  vm.poweroff matches that; vm.stop would do a
        # clean ACPI shutdown and wait shutdown_timeout, which is the wrong
        # semantics for tests that expect an abrupt power event.
        with _tn_client(cfg) as c:
            return c.call('vm.poweroff', _tn_vm_id(c, vmname))
    command = ['destroy', vmname]
    if graceful:
        command.append('--graceful')
    return _virsh(command)


def reset_vm(vmname):
    if cfg := _tn_test_config():
        with _tn_client(cfg) as c:
            return c.call('vm.reset', _tn_vm_id(c, vmname))
    return _virsh(['reset', vmname])


def shutdown_vm(vmname, mode='acpi'):
    if cfg := _tn_test_config():
        # The virsh --mode selector (acpi/agent/signal/...) has no direct
        # equivalent in the TrueNAS vm API; vm.stop performs an ACPI shutdown.
        with _tn_client(cfg) as c:
            return c.call('vm.stop', _tn_vm_id(c, vmname), {}, job=True)
    return _virsh(['shutdown', vmname, '--mode', mode])


def start_vm(vmname, force_boot=False):
    if cfg := _tn_test_config():
        # No --force-boot equivalent in the TrueNAS vm API; force_boot is ignored.
        with _tn_client(cfg) as c:
            return c.call('vm.start', _tn_vm_id(c, vmname))
    command = ['start', vmname]
    if force_boot:
        command.append('--force-boot')
    return _virsh(command)
