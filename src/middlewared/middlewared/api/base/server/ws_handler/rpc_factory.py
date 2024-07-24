from ..method import Method
from .rpc import RpcWebSocketHandler


def create_rpc_ws_handler(middleware: "Middleware"):
    methods = {}
    for service_name, service in middleware.get_services().items():
        for attribute in dir(service):
            if attribute.startswith("_"):
                continue

            if not callable(getattr(service, attribute)):
                continue

            method_name = f"{service_name}.{attribute}"

            methods[method_name] = Method(middleware, method_name)

    return RpcWebSocketHandler(middleware, methods)
