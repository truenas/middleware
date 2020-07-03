from .connection import LibvirtConnectionMixin


class VMSupervisorMixin(LibvirtConnectionMixin):

    vms = {}
