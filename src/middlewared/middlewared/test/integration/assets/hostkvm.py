import os
import re
import shlex

from middlewared.test.integration.utils import call, run_on_runner, RunOnRunnerException, ssh

try:
    from config import KVM_HOST, KVM_PASSWORD, KVM_USERNAME
    have_kvm_host_cfg = True
except ImportError:
    have_kvm_host_cfg = False

TM_NODE_RE = re.compile('^tm[0-9]{3}$')
HA_NODE_RE = re.compile('^ha[0-9]{3}_c[1|2]$')
WHOLE_HA_NODE_RE = re.compile('^ha[0-9]{3}$')


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


def poweroff_vm(vmname):
    """
    Issue a virsh destroy <domain>.  This is similar to pulling the power
    cable.  The VM can be restarted later.
    """
    return _virsh(['destroy', vmname])


def reset_vm(vmname):
    return _virsh(['reset', vmname])


def shutdown_vm(vmname, mode='acpi'):
    return _virsh(['shutdown', vmname, '--mode', mode])


def start_vm(vmname, force_boot=False):
    command = ['start', vmname]
    if force_boot:
        command.append('--force-boot')
    return _virsh(command)
