from middlewared.service import private, ServicePartBase


class FailoverChecksBase(ServicePartBase):

    @private
    async def nic_capability_checks(self, vm_devices=None, check_system_iface=True):
        """
        For NIC devices, if VM is started and NIC is added to a bridge, if desired nic_attach NIC has certain
        capabilities set, we experience a hiccup in the network traffic which can cause a failover to occur.
        This method returns interfaces which will be affected by this.
        """
