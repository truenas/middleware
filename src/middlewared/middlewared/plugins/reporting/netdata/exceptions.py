from middlewared.service import CallError


class ApiException(CallError):
    pass
