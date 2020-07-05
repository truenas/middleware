import math

from middlewared.service import Service

from .vm_validation_base import VMValidationBase


class VMService(Service, VMValidationBase):

    def validate_slots(self, vm_data):
        return False

    async def validate_vcpus(self, vcpus, schema_name, verrors):
        pass
