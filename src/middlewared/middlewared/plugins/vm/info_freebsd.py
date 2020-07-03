import sysctl

from middlewared.service import Service

from .info_base import VMInfoBase


class VMService(Service, VMInfoBase):

    def supports_virtualization(self):
        flags = self.flags()
        return not flags['intel_vmx'] and not flags['amd_rvi']

    def available_slots(self):
        return 29  # 3 slots are being used by libvirt / bhyve

    def flags(self):
        data = {}
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
