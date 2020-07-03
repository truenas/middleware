from middlewared.service import private, ServicePartBase


class VMValidationBase(ServicePartBase):

    @private
    def validate_slots(self, vm_data):
        """
        Returns True if their aren't enough slots to support all the devices configured, False otherwise
        """

    @private
    def validate_vcpus(self, vcpus, schema_name, verrors):
        raise NotImplementedError
