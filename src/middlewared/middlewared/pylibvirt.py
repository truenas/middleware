import time
from typing import Callable

from truenas_pylibvirt import BaseDomain, Connection, ConnectionManager, DomainManagers, ServiceDelegate

__all__ = ["create_pylibvirt_domains_manager", "gather_pylibvirt_domains_states", "get_pylibvirt_domain_state"]


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


def gather_pylibvirt_domains_states(
    middleware,
    rows: list[dict],
    connection: Connection,
    container_factory: Callable[[dict], BaseDomain],
):
    state = {}
    if rows:
        shutting_down = middleware.call_sync('system.state') == 'SHUTTING_DOWN'
        if not shutting_down:
            uuid_to_container = {row['uuid']: row for row in rows}
            try:
                for domain in connection.list_domains():
                    uuid = domain.name()
                    if container := uuid_to_container.get(uuid):
                        state[uuid] = pylibvirt_domain_state(
                            connection,
                            domain,
                            container_factory(container.copy()),
                        )
            except Exception:
                middleware.logger.warning("Unhandled exception in gather_pylibvirt_domains_state", exc_info=True)

    return state


def pylibvirt_domain_state(
    connection: Connection,
    libvirt_domain,
    domain: BaseDomain,
):
    domain_state = connection.domain_state(libvirt_domain).value
    if libvirt_domain.isActive():
        state = 'SUSPENDED' if domain_state == 'PAUSED' else 'RUNNING'
    else:
        state = 'STOPPED'

    return {
        'state': state,
        'pid': domain.pid(),
        'domain_state': domain_state,
    }


def get_pylibvirt_domain_state(gathered_states: dict, domain: dict):
    return gathered_states.get(domain['uuid']) or {
        'state': 'STOPPED',
        'pid': None,
        'domain_state': None,
    }
