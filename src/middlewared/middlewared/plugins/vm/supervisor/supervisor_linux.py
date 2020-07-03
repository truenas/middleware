from .supervisor_base import VMSupervisorBase


class VMSupervisor(VMSupervisorBase):

    def construct_xml(self):
        raise NotImplementedError

    def commandline_xml(self):
        raise NotImplementedError

    def commandline_args(self):
        raise NotImplementedError

    def os_xml(self):
        raise NotImplementedError

    def devices_xml(self):
        raise NotImplementedError
