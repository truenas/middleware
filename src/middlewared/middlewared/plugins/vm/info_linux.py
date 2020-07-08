import os
import re

from middlewared.service import Service
from middlewared.utils import run

from .info_base import VMInfoBase


RE_AMD_NASID = re.compile(r'NASID:.*\((.*)\)')
RE_VENDOR_AMD = re.compile(r'AuthenticAMD')
RE_VENDOR_INTEL = re.compile(r'GenuineIntel')


class VMService(Service, VMInfoBase):

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
