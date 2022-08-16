import contextlib

from middlewared.service import CallError

from .connection import LibvirtConnectionMixin
from .supervisor import VMSupervisor
from .utils import ACTIVE_STATES


class VMSupervisorMixin(LibvirtConnectionMixin):

    vms = {}

    def _add(self, vm_id):
        vm = self.middleware.call_sync('vm.get_instance', vm_id)
        self._add_with_vm_data(vm)

    def _add_with_vm_data(self, vm):
        self.vms[vm['name']] = VMSupervisor(vm, self.middleware)

    def _has_domain(self, vm_name):
        return vm_name in self.vms and self.vms[vm_name].domain

    def _rename_domain(self, old, new):
        vm = self.vms.pop(old['name'])
        vm.update_domain(new)
        self.vms[new['name']] = vm

    def _clear(self):
        VMSupervisorMixin.vms = {}

    def _vm_from_name(self, vm_name):
        return self.middleware.call_sync('vm.query', [['name', '=', vm_name]], {'get': True, 'force_sql_filters': True})

    def _undefine_domain(self, vm_name):
        domain = self.vms.pop(vm_name, None)
        if domain and domain.domain:
            domain.undefine_domain()
        else:
            VMSupervisor(self._vm_from_name(vm_name), self.middleware).undefine_domain()

    def _check_add_domain(self, vm_name):
        if not self._has_domain(vm_name):
            try:
                self._add(self._vm_from_name(vm_name)['id'])
            except Exception as e:
                raise CallError(f'Unable to define domain for {vm_name}: {e}')
        if not self._has_domain(vm_name):
            raise CallError(f'Libvirt domain for {vm_name} does not exist')

    def _check_domain_status(self, vm_name, desired_status='RUNNING'):
        if not self._has_domain(vm_name):
            raise CallError(f'Libvirt Domain for {vm_name} does not exist')

        desired_status = desired_status if isinstance(desired_status, list) else [desired_status]
        configured_status = 'ERROR'
        with contextlib.suppress(Exception):
            configured_status = self._status(vm_name)['state']

        if configured_status == 'ERROR':
            raise CallError(f'Unable to determine {vm_name!r} VM state')

        if configured_status not in desired_status:
            raise CallError(f'VM state is currently not {" / ".join(desired_status)!r}')

    def _start(self, vm_name):
        self._check_add_domain(vm_name)
        self.vms[vm_name].start(vm_data=self._vm_from_name(vm_name))

    def _poweroff(self, vm_name):
        self._check_domain_status(vm_name, ACTIVE_STATES)
        self.vms[vm_name].poweroff()

    def _stop(self, vm_name, shutdown_timeout):
        self._check_domain_status(vm_name)
        self.vms[vm_name].stop(shutdown_timeout)

    def _suspend(self, vm_name):
        self._check_domain_status(vm_name)
        self.vms[vm_name].suspend()

    def _resume(self, vm_name):
        self._check_domain_status(vm_name, 'PAUSED')
        self.vms[vm_name].resume()

    def _status(self, vm_name):
        self._check_setup_connection()
        return self.vms[vm_name].status()

    def _memory_info(self, vm_name):
        self._check_setup_connection()
        self._check_domain_status(vm_name, ACTIVE_STATES)
        return self.vms[vm_name].memory_usage()
