import os
import stat
import sysctl

from middlewared.service import Service

from .info_base import VMInfoBase


class VMService(Service, VMInfoBase):

    async def supports_virtualization(self):
        flags = await self.middleware.call('vm.flags')
        return flags['intel_vmx'] or flags['amd_rvi']

    async def maximum_supported_vcpus(self):
        return 16

    def flags(self):
        data = self.flags_base.copy()
        intel = True if 'Intel' in sysctl.filter('hw.model')[0].value else False

        vmx = sysctl.filter('hw.vmm.vmx.initialized')
        data['intel_vmx'] = True if vmx and vmx[0].value else False

        ug = sysctl.filter('hw.vmm.vmx.cap.unrestricted_guest')
        data['unrestricted_guest'] = True if ug and ug[0].value else False

        # If virtualization is not supported on AMD, the sysctl value will be -1 but as an unsigned integer
        # we should make sure we check that accordingly.
        rvi = sysctl.filter('hw.vmm.svm.features')
        data['amd_rvi'] = True if rvi and rvi[0].value != 0xffffffff and not intel else False

        asids = sysctl.filter('hw.vmm.svm.num_asids')
        data['amd_asids'] = True if asids and asids[0].value != 0 else False

        return data

    async def get_console(self, id):
        try:
            guest_status = await self.middleware.call('vm.status', id)
        except Exception:
            guest_status = None

        if guest_status and guest_status['state'] == 'RUNNING':
            device = '/dev/nmdm{0}B'.format(id)
            if stat.S_ISCHR(os.stat(device).st_mode) is True:
                return device

        return False
