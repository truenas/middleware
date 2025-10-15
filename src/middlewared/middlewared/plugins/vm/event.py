import functools
import logging

from truenas_pylibvirt.libvirtd.connection import DomainState


logger = logging.getLogger(__name__)


STOPPED_STATES = [DomainState.SHUTDOWN, DomainState.SHUTOFF, DomainState.CRASHED]


def vm_domain_event_callback(middleware, event):
    """
    Handle VM domain lifecycle events from libvirt.

    Sends CHANGED events for all libvirt state changes and cleans up memory on stop.
    VM CRUD events (create/update/delete) are handled automatically by CRUDService.
    """
    vm = middleware.call_sync('vm.query', [['uuid', '=', event.uuid]], {'force_sql_filters': True})
    if not vm:
        return

    middleware.send_event('vm.query', 'CHANGED', id=vm[0]['id'], fields=vm[0])


async def setup(middleware):
    middleware.libvirt_domains_manager.vms.connection.register_domain_event_callback(
        functools.partial(vm_domain_event_callback, middleware)
    )
