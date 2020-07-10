from middlewared.service import Service

from .failover_check_base import FailoverChecksBase


class VMDeviceService(Service, FailoverChecksBase):

    class Config:
        namespace = 'vm.device'

    def nic_capability_checks(self, vm_devices=None, check_system_iface=True):
        raise NotImplementedError
