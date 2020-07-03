from middlewared.service import accepts, private, ServicePartBase


class VMInfoBase(ServicePartBase):

    @accepts()
    async def supports_virtualization(self):
        """
        Returns "true" if system supports virtualization, "false" otherwise
        """

    @accepts()
    async def available_slots(self):
        """
        Returns available number of slots which can be used for attaching devices to a VM
        """

    @accepts()
    def flags(self):
        """
        Returns a dictionary with CPU flags for the hypervisor.
        """
