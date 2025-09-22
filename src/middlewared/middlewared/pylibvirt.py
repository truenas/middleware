import time

from truenas_pylibvirt import ConnectionManager, DomainManagers, ServiceDelegate

__all__ = ["create_pylibvirt_domains_manager"]


class MiddlewareServiceDelegate(ServiceDelegate):
    def __init__(self, middleware):
        self.middleware = middleware

    def ensure_started(self):
        self.middleware.call_sync("service.control", "START", "libvirtd").wait_sync(raise_error=True)
        while not self.middleware.call_sync("service.started", "libvirtd"):
            time.sleep(2)

    def stop(self):
        self.middleware.call_sync("service.control", "STOP", "libvirtd").wait_sync(raise_error=True)


def create_pylibvirt_domains_manager(middleware):
    connection_manager = ConnectionManager(MiddlewareServiceDelegate(middleware))
    domains_manager = DomainManagers(connection_manager)
    return domains_manager
