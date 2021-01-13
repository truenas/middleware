import os
import re
import subprocess

from lxml import etree

from middlewared.service import accepts, Service
from middlewared.utils import run

from .info_base import VMInfoBase
from .utils import get_virsh_command_args


RE_AMD_NASID = re.compile(r'NASID:.*\((.*)\)')
RE_VENDOR_AMD = re.compile(r'AuthenticAMD')
RE_VENDOR_INTEL = re.compile(r'GenuineIntel')


class VMService(Service, VMInfoBase):

    CPU_MODEL_CHOICES = {}

    async def supports_virtualization(self):
        cp = await run(['kvm-ok'], check=False)
        return cp.returncode == 0

    async def maximum_supported_vcpus(self):
        return 255

    async def flags(self):
        flags = self.flags_base.copy()
        supports_vm = await self.supports_virtualization()
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

    async def get_console(self, id):
        vm = await self.middleware.call('vm.get_instance', id)
        return f'{vm["id"]}_{vm["name"]}'

    @accepts()
    def cpu_model_choices(self):
        """
        Retrieve CPU Model choices which can be used with a VM guest to emulate the CPU in the guest.
        """
        base_path = '/usr/share/libvirt/cpu_map'
        if self.CPU_MODEL_CHOICES or not os.path.exists(base_path):
            return self.CPU_MODEL_CHOICES

        mapping = {}
        with open(os.path.join(base_path, 'index.xml'), 'r') as f:
            index_xml = etree.fromstring(f.read().strip())

        for arch in filter(lambda a: a.tag == 'arch' and a.get('name'), index_xml.getchildren()):
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
