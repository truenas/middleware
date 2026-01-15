class NetlinkError(Exception):
    pass


class DeviceNotFound(NetlinkError):
    pass


class OperationNotSupported(NetlinkError):
    pass


class DumpInterrupted(NetlinkError):
    pass
