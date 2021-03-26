from abc import ABC

from middlewared.utils import osc


class Device(ABC):

    schema = NotImplemented

    def __init__(self, data, middleware=None):
        self.data = data
        self.middleware = middleware

    def xml(self, *args, **kwargs):
        return getattr(self, f'xml_{osc.SYSTEM.lower()}')(*args, **kwargs)

    def is_available(self):
        raise NotImplementedError

    def xml_freebsd(self, *args, **kwargs):
        raise NotImplementedError

    def xml_linux(self, *args, **kwargs):
        raise NotImplementedError

    def pre_start_vm(self, *args, **kwargs):
        return getattr(self, f'pre_start_vm_{osc.SYSTEM.lower()}')(*args, **kwargs)

    def pre_start_vm_linux(self, *args, **kwargs):
        pass

    def pre_start_vm_freebsd(self, *args, **kwargs):
        pass

    def pre_start_vm_rollback(self, *args, **kwargs):
        return getattr(self, f'pre_start_vm_rollback_{osc.SYSTEM.lower()}')(*args, **kwargs)

    def pre_start_vm_rollback_linux(self, *args, **kwargs):
        pass

    def pre_start_vm_rollback_freebsd(self, *args, **kwargs):
        pass

    def post_start_vm(self, *args, **kwargs):
        return getattr(self, f'post_start_vm_{osc.SYSTEM.lower()}')(*args, **kwargs)

    def post_start_vm_linux(self, *args, **kwargs):
        pass

    def post_start_vm_freebsd(self, *args, **kwargs):
        pass

    def post_stop_vm(self, *args, **kwargs):
        return getattr(self, f'post_stop_vm_{osc.SYSTEM.lower()}')(*args, **kwargs)

    def post_stop_vm_linux(self, *args, **kwargs):
        pass

    def post_stop_vm_freebsd(self, *args, **kwargs):
        pass

    def hypervisor_args(self, *args, **kwargs):
        return getattr(self, f'hypervisor_args_{osc.SYSTEM.lower()}')(*args, **kwargs)

    def hypervisor_args_linux(self, *args, **kwargs):
        pass

    def hypervisor_args_freebsd(self, *args, **kwargs):
        pass

    def __str__(self):
        return f'{self.__class__.__name__} Device: {self.identity()}'

    def identity(self):
        raise NotImplementedError

    def pre_start_vm_device_setup(self, *args, **kwargs):
        return getattr(self, f'pre_start_vm_device_setup_{osc.SYSTEM.lower()}')(*args, **kwargs)

    def pre_start_vm_device_setup_linux(self, *args, **kwargs):
        pass

    def pre_start_vm_device_setup_freebsd(self, *args, **kwargs):
        pass
