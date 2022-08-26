import libvirt
import threading

from middlewared.service import private, Service

from .connection import LibvirtConnectionMixin


class VMService(Service, LibvirtConnectionMixin):

    @private
    def setup_libvirt_events(self):
        self._check_setup_connection()

        def callback(conn, dom, event, detail, opaque):
            """
            0: 'DEFINED',
            1: 'UNDEFINED',
            2: 'STARTED',
            3: 'SUSPENDED',
            4: 'RESUMED',
            5: 'STOPPED',
            6: 'SHUTDOWN',
            7: 'PMSUSPENDED'
            Above is event mapping for internal reference
            """
            vm_id = dom.name().split('_')[0]
            vm = None
            if vm_id.isdigit():
                if vms := self.middleware.call_sync('vm.query', [['id', '=', int(vm_id)]], {'force_sql_filters': True}):
                    if dom.name() == f'{vms[0]["id"]}_{vms[0]["name"]}':
                        vm = vms[0]

            if vm is None:
                emit_type = 'REMOVED'
            elif event == 0:
                emit_type = 'ADDED'
            else:
                emit_type = 'CHANGED'

            vm_state_mapping = {
                0: 'NOSTATE',
                1: 'RUNNING',
                2: 'BLOCKED',
                3: 'SUSPENDED',  # Actual libvirt event here is PAUSED
                4: 'SHUTDOWN',
                5: 'SHUTOFF',
                6: 'CRASHED',
                7: 'PMSUSPENDED',
            }
            try:
                if event == 1:
                    if emit_type == 'REMOVED':
                        state = 'NOSTATE'
                    else:
                        # We undefine/define domain numerous times based on if vm has any new changes
                        # registered, this is going to reflect that
                        state = 'UPDATING CONFIGURATION'
                else:
                    state = vm_state_mapping.get(dom.state()[0], 'UNKNOWN')
            except libvirt.libvirtError:
                state = 'UNKNOWN'

            # We do not send an event on removed because that would already be done by vm.delete
            if vm is not None:
                vm['status']['state'] = state
                self.middleware.send_event(
                    'vm.query', emit_type, id=int(vm_id), fields=vm, state=vm_state_mapping.get(event, 'UNKNOWN')
                )

        def event_loop_execution():
            while self.LIBVIRT_CONNECTION and self.LIBVIRT_CONNECTION._o and self.LIBVIRT_CONNECTION.isAlive():
                libvirt.virEventRunDefaultImpl()

        event_thread = threading.Thread(target=event_loop_execution, name='libvirt_event_loop')
        event_thread.setDaemon(True)
        event_thread.start()
        self.LIBVIRT_CONNECTION.domainEventRegister(callback, None)
        self.LIBVIRT_CONNECTION.setKeepAlive(5, 3)
