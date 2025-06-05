import os
import re
import subprocess
from xml.etree import ElementTree as etree

from middlewared.api import api_method
from middlewared.api.current import (
    VMSupportsVirtualizationArgs, VMSupportsVirtualizationResult, VMVirtualizationDetailsArgs,
    VMVirtualizationDetailsResult, VMMaximumSupportedVCPUsArgs, VMMaximumSupportedVCPUsResult, VMFlagsArgs,
    VMFlagsResult, VMGetConsoleArgs, VMGetConsoleResult, VMCPUModelChoicesArgs, VMCPUModelChoicesResult,
)
from middlewared.service import private, Service
from middlewared.utils import run

from .connection import LibvirtConnectionMixin
from .utils import get_virsh_command_args


RE_AMD_NASID = re.compile(r'NASID:.*\((.*)\)')
RE_VENDOR_AMD = re.compile(r'AuthenticAMD')
RE_VENDOR_INTEL = re.compile(r'GenuineIntel')


class VMService(Service, LibvirtConnectionMixin):

    CPU_MODEL_CHOICES = {}

    @api_method(VMSupportsVirtualizationArgs, VMSupportsVirtualizationResult, roles=['VM_READ'])
    def supports_virtualization(self):
        """
        Returns "true" if system supports virtualization, "false" otherwise
        """
        return self._is_kvm_supported()

    @private
    async def license_active(self):
        """
        If this is HA capable hardware and has NOT been licensed to run VMs
        then this will return False. Otherwise this will return true.
        """
        can_run_vms = True
        if await self.middleware.call('system.is_ha_capable'):
            license_ = await self.middleware.call('system.license')
            can_run_vms = license_ is not None and 'VM' in license_['features']

        return can_run_vms

    @api_method(VMVirtualizationDetailsArgs, VMVirtualizationDetailsResult, roles=['VM_READ'])
    def virtualization_details(self):
        """
        Retrieve details if virtualization is supported on the system and in case why it's not supported if it isn't.
        """
        return {
            'supported': self._is_kvm_supported(),
            'error': None if self._is_kvm_supported() else 'Your CPU does not support KVM extensions',
        }

    @api_method(VMMaximumSupportedVCPUsArgs, VMMaximumSupportedVCPUsResult, roles=['VM_READ'])
    async def maximum_supported_vcpus(self):
        """
        Returns maximum supported VCPU's
        """
        return 255

    @api_method(VMFlagsArgs, VMFlagsResult, roles=['VM_READ'])
    async def flags(self):
        """
        Returns a dictionary with CPU flags for the hypervisor.
        """
        flags = {
            'intel_vmx': False,
            'unrestricted_guest': False,
            'amd_rvi': False,
            'amd_asids': False,
        }
        supports_vm = await self.middleware.call('vm.supports_virtualization')
        if not supports_vm:
            return flags

        cp = await run(['lscpu'], check=False)
        if cp.returncode:
            self.middleware.logger.error('Failed to retrieve CPU details: %s', cp.stderr.decode())
            return flags

        if RE_VENDOR_INTEL.findall(cp.stdout.decode()):
            flags['intel_vmx'] = True
            unrestricted_guest_path = '/sys/module/kvm_intel/parameters/unrestricted_guest'
            if os.path.exists(unrestricted_guest_path):
                with open(unrestricted_guest_path, 'r') as f:
                    flags['unrestricted_guest'] = f.read().strip().lower() == 'y'
        elif RE_VENDOR_AMD.findall(cp.stdout.decode()):
            flags['amd_rvi'] = True
            cp = await run(['cpuid', '-l', '0x8000000A'], check=False)
            if cp.returncode:
                self.middleware.logger.error('Failed to execute "cpuid -l 0x8000000A": %s', cp.stderr.decode())
            else:
                flags['amd_asids'] = all(v != '0' for v in (RE_AMD_NASID.findall(cp.stdout.decode()) or ['0']) if v)

        return flags

    @api_method(VMGetConsoleArgs, VMGetConsoleResult, roles=['VM_READ'])
    async def get_console(self, id_):
        """
        Get the console device from a given guest.
        """
        vm = await self.middleware.call('vm.get_instance', id_)
        return f'{vm["id"]}_{vm["name"]}'

    @api_method(VMCPUModelChoicesArgs, VMCPUModelChoicesResult, roles=['VM_READ'])
    def cpu_model_choices(self):
        """
        Retrieve CPU Model choices which can be used with a VM guest to emulate the CPU in the guest.
        """
        self.middleware.call_sync('vm.check_setup_libvirt')
        base_path = '/usr/share/libvirt/cpu_map'
        if self.CPU_MODEL_CHOICES or not os.path.exists(base_path):
            return self.CPU_MODEL_CHOICES

        mapping = {}
        with open(os.path.join(base_path, 'index.xml'), 'r') as f:
            index_xml = etree.fromstring(f.read().strip())

        for arch in filter(lambda a: a.tag == 'arch' and a.get('name'), list(index_xml)):
            cp = subprocess.Popen(
                get_virsh_command_args() + ['cpu-models', arch.get('name') if arch.get('name') != 'x86' else 'x86_64'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout = cp.communicate()[0]
            if cp.returncode:
                continue
            mapping.update({m: m for m in filter(bool, stdout.decode().strip().split('\n'))})

        self.CPU_MODEL_CHOICES.update(mapping)
        return self.CPU_MODEL_CHOICES
