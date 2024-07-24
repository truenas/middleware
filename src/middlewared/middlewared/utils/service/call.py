# -*- coding=utf-8 -*-
import errno
import logging

from middlewared.service_exception import CallError

logger = logging.getLogger(__name__)

__all__ = ["MethodNotFoundError", "ServiceCallMixin"]


class MethodNotFoundError(CallError):
    def __init__(self, method_name, service):
        super().__init__(f'Method {method_name!r} not found in {service!r}', CallError.ENOMETHOD)


class ServiceCallMixin:
    def get_method(self, name):
        if '.' not in name:
            raise CallError('Invalid method name', errno.EBADMSG)

        service, method_name = name.rsplit('.', 1)

        try:
            serviceobj = self.get_service(service)
        except KeyError:
            raise CallError(f'Service {service!r} not found', CallError.ENOMETHOD)

        try:
            methodobj = getattr(serviceobj, method_name)
        except AttributeError:
            raise MethodNotFoundError(method_name, service)

        return serviceobj, methodobj
