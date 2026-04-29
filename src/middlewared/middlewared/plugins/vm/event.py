from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api.current import QueryOptions

if TYPE_CHECKING:
    from truenas_pylibvirt.libvirtd.connection import DomainEvent

    from middlewared.main import Middleware


def vm_domain_event_callback(middleware: Middleware, event: DomainEvent) -> None:
    """
    Handle VM domain lifecycle events from libvirt.

    Sends CHANGED events for all libvirt state changes and cleans up memory on stop.
    VM CRUD events (create/update/delete) are handled automatically by CRUDService.
    """
    vms = middleware.call_sync2(
        middleware.services.vm.query, [["uuid", "=", event.uuid]], QueryOptions(force_sql_filters=True)
    )
    if not vms:
        return

    vm = vms[0]
    middleware.send_event("vm.query", "CHANGED", id=vm.id, fields=vm.model_dump(by_alias=True))
