from middlewared.service import CallError

from .connection import LibvirtConnectionMixin
from .supervisor import VMSupervisor


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
        return self.middleware.call_sync('vm.query', [['name', '=', vm_name]], {'get': True})

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

    def _check_domain_running(self, vm_name):
        if not self._has_domain(vm_name):
            raise CallError(f'Libvirt Domain for {vm_name} does not exist')
        error = True
        try:
            error = self._status(vm_name)['state'] == 'ERROR'
        except Exception:
            pass
        finally:
            if error:
                raise CallError(f'Unable to determine {vm_name} VM state')

    def _start(self, vm_name):
        self._check_add_domain(vm_name)
        self.vms[vm_name].start(vm_data=self._vm_from_name(vm_name))

    def _poweroff(self, vm_name):
        self._check_domain_running(vm_name)
        self.vms[vm_name].poweroff()

    def _stop(self, vm_name, shutdown_timeout):
        self._check_domain_running(vm_name)
        self.vms[vm_name].stop(shutdown_timeout)

    def _restart(self, vm_name):
        self._check_domain_running(vm_name)
        vm = self._vm_from_name(vm_name)
        self.vms[vm_name].restart(vm_data=vm, shutdown_timeout=vm['shutdown_timeout'])

    def _status(self, vm_name):
        self._check_setup_connection()
        return self.vms[vm_name].status()
