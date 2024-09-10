from typing import Callable, TYPE_CHECKING

from ..method import Method
from .rpc import RpcWebSocketHandler

if TYPE_CHECKING:
    from middlewared.main import Middleware


def create_rpc_ws_handler(middleware: "Middleware", method_factory: Callable[["Middleware", str], Method]):
    """
    Creates a `RpcWebSocketHandler` instance.
    :param middleware: `Middleware` instance.
    :param method_factory: a callable that creates `Method` instance. Will be called for each discovered middleware
        method.
    :return: `RpcWebSocketHandler` instance.
    """
    methods = {}
    for service_name, service in middleware.get_services().items():
        for attribute in dir(service):
            if attribute.startswith("_"):
                continue

            if not callable(getattr(service, attribute)):
                continue

            method_name = f"{service_name}.{attribute}"

            methods[method_name] = method_factory(middleware, method_name)

    return RpcWebSocketHandler(middleware, methods)
