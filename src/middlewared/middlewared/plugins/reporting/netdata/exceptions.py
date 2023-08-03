from middlewared.service import CallError


class ApiException(CallError):
    pass


class ClientConnectError(CallError):
    pass
