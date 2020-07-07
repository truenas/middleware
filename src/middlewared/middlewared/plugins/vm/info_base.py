from middlewared.schema import Int
from middlewared.service import accepts, ServicePartBase


class VMInfoBase(ServicePartBase):

    flags_base = {
        'intel_vmx': False,
        'unrestricted_guest': False,
        'amd_rvi': False,
        'amd_asids': False,
    }

    @accepts()
    async def supports_virtualization(self):
        """
        Returns "true" if system supports virtualization, "false" otherwise
        """

    @accepts()
    async def maximum_supported_vcpus(self):
        """
        Returns maximum supported VCPU's
        """

    @accepts()
    def flags(self):
        """
        Returns a dictionary with CPU flags for the hypervisor.
        """

    @accepts(Int('id'))
    async def get_console(self, id):
        """
        Get the console device from a given guest.

        Returns:
            str: with the device path or False.
        """
