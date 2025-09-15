from abc import ABC

from middlewared.api.base.handler.accept import validate_model
from middlewared.service_exception import ValidationErrors


class Device(ABC):

    schema_model = NotImplementedError

    def __init__(self, data, middleware=None):
        self.data = data
        self.middleware = middleware

    def xml(self, *args, **kwargs):
        raise NotImplementedError

    def is_available(self):
        raise NotImplementedError

    def pre_start_vm(self, *args, **kwargs):
        pass

    def pre_start_vm_rollback(self, *args, **kwargs):
        pass

    def post_start_vm(self, *args, **kwargs):
        pass

    def post_stop_vm(self, *args, **kwargs):
        pass

    def __str__(self):
        return f'{self.__class__.__name__} Device: {self.identity()}'

    def identity(self):
        raise NotImplementedError

    def pre_start_vm_device_setup(self, *args, **kwargs):
        pass

    def validate(self, device, old=None, vm_instance=None, update=True):
        if self.schema_model is NotImplementedError:
            raise NotImplementedError('schema_model is not implemented for this device')

        dump = validate_model(self.schema_model, device['attributes'])
        device['attributes'] = dump
        verrors = ValidationErrors()
        self._validate(device, verrors, old, vm_instance, update)
        verrors.check()

    def _validate(self, device, verrors, old=None, vm_instance=None, update=True):
        raise NotImplementedError
