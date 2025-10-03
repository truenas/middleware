import functools
import logging

from middlewared.service import private, Service

from truenas_pylibvirt.libvirtd.connection import DomainState

logger = logging.getLogger(__name__)


VM_STATE_MAPPING = {
    DomainState.NOSTATE: 'NOSTATE',        # No state information available
    DomainState.RUNNING: 'RUNNING',        # Domain is actively running
    DomainState.BLOCKED: 'BLOCKED',        # Domain is blocked on I/O
    DomainState.SUSPENDED: 'SUSPENDED',    # Domain is suspended/paused (libvirt PAUSED state)
    DomainState.SHUTDOWN: 'SHUTDOWN',      # Domain is being shut down
    DomainState.SHUTOFF: 'SHUTOFF',        # Domain is completely shut off
    DomainState.CRASHED: 'CRASHED',        # Domain has crashed
    DomainState.PMSUSPENDED: 'PMSUSPENDED',  # Domain suspended by guest power management
}

STOPPED_STATES = ['STOPPED', 'SHUTOFF', 'CRASHED']


def vm_domain_event_callback(middleware, event):
    """
    Handle VM domain lifecycle events from pylibvirt.

    This callback is triggered by libvirt domain events and handles:
    - VM state changes and middleware event emission
    - Memory management for stopped VMs
    - Configuration update tracking

    Libvirt Domain Event Types (for reference):
        0: 'DEFINED'      - Domain configuration has been defined/created
        1: 'UNDEFINED'    - Domain configuration has been undefined/deleted
        2: 'STARTED'      - Domain has started (transitioned to running)
        3: 'SUSPENDED'    - Domain has been suspended/paused
        4: 'RESUMED'      - Domain has resumed from suspended state
        5: 'STOPPED'      - Domain has stopped (shutdown gracefully)
        6: 'SHUTDOWN'     - Domain is in process of shutting down
        7: 'PMSUSPENDED'  - Domain has been suspended by guest power management

    Note: The event.uuid contains the domain name (which is the VM UUID in our case)
    """
    # Try to find VM by UUID - using uuid field since event.uuid is the domain name
    vm = middleware.call_sync('vm.query', [['uuid', '=', event.uuid]], {'force_sql_filters': True})

    # If VM not found, it might have been deleted
    if not vm:
        # Try extracting the VM ID from the UUID if it follows the pattern
        # But for now, just return as VM is already gone
        logger.debug(f"VM with UUID {event.uuid} not found, likely deleted")
        return

    vm = vm[0]
    vm.pop('devices', None)  # Remove devices from event payload for efficiency

    # Get current state from libvirt through pylibvirt
    try:
        # Get the libvirt domain through the connection
        libvirt_domain = middleware.libvirt_domains_manager.vms.connection.get_domain(event.uuid)
        if libvirt_domain is None:
            # Domain was removed
            vm['status']['state'] = 'NOSTATE'
            emit_type = 'REMOVED'
        else:
            # Get the actual state from libvirt
            domain_state = middleware.libvirt_domains_manager.vms.connection.domain_state(libvirt_domain)
            state = VM_STATE_MAPPING.get(domain_state, 'UNKNOWN')
            vm['status']['state'] = state

            # Determine event type based on state
            if state == 'RUNNING' and vm.get('status', {}).get('state') != 'RUNNING':
                emit_type = 'ADDED'
            else:
                emit_type = 'CHANGED'

            # Handle VM stopped event - teardown memory
            if state in STOPPED_STATES:
                logger.info(f"VM {vm['name']} stopped (state: {state}), releasing memory")
                try:
                    middleware.call_sync('vm.teardown_guest_vmemory', vm['id'])
                except Exception:
                    logger.error(f"Failed to teardown memory for VM {vm['name']}", exc_info=True)
    except Exception:
        logger.error(f"Failed to get status for VM {vm['name']}", exc_info=True)
        vm['status']['state'] = 'UNKNOWN'
        emit_type = 'CHANGED'

    # Send event to subscribers with updated state
    # Event types:
    #   - ADDED: VM has transitioned to running state
    #   - CHANGED: VM state has changed (suspended, stopped, etc.)
    #   - REMOVED: VM domain has been undefined/deleted
    middleware.send_event(
        'vm.query', emit_type,
        id=vm['id'],
        fields=vm,
        state=vm['status']['state']
    )


class VMService(Service):

    @private
    def setup_libvirt_events(self):
        self.middleware.libvirt_domains_manager.vms.connection.register_domain_event_callback(
            functools.partial(vm_domain_event_callback, self.middleware)
        )


async def setup(middleware):
    # Need to handle boot + HA case
    if await middleware.call('system.ready'):
        await middleware.call('vm.setup_libvirt_events')
