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
            vms = {f'{d["id"]}_{d["name"]}': d for d in self.middleware.call_sync('vm.query')}
            if dom.name() not in vms:
                emit_type = 'REMOVED'
            elif event == 0:
                emit_type = 'ADDED'
            else:
                emit_type = 'CHANGED'

            vm_state_mapping = {
                0: 'NOSTATE',
                1: 'RUNNING',
                2: 'BLOCKED',
                3: 'PAUSED',
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

            vm_id = dom.name().split('_')[0]
            if vm_id.isdigit():
                self.middleware.send_event('vm.query', emit_type, id=int(vm_id), fields={'state': state})
            else:
                self.middleware.logger.debug('Received libvirtd event with unknown domain name %s', dom.name())

        def event_loop_execution():
            while self.LIBVIRT_CONNECTION and self.LIBVIRT_CONNECTION._o and self.LIBVIRT_CONNECTION.isAlive():
                libvirt.virEventRunDefaultImpl()

        event_thread = threading.Thread(target=event_loop_execution, name='libvirt_event_loop')
        event_thread.setDaemon(True)
        event_thread.start()
        self.LIBVIRT_CONNECTION.domainEventRegister(callback, None)
        self.LIBVIRT_CONNECTION.setKeepAlive(5, 3)
