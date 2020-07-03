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
        return vm_name in self.vms

    def _rename_domain(self, old, new):
        vm = self.vms.pop(old['name'])
        vm.update_domain(new)
        self.vms[new['name']] = vm

    def _clear(self):
        self.vms = {}

    def _vm_from_name(self, vm_name):
        return self.middleware.call_sync('vm.query', [['name', '=', vm_name]], {'get': True})

    def _undefine_domain(self, vm_name):
        if self._has_domain(vm_name):
            self.vms.pop(vm_name).undefine_domain()
        else:
            VMSupervisor(self._vm_from_name(vm_name)).undefine_domain()

    def _start(self, vm_name):
        self.vms[vm_name].start(vm_data=self._vm_from_name(vm_name))

    def _poweroff(self, vm_name):
        self.vms[vm_name].poweroff()

    def _stop(self, vm_name, shutdown_timeout):
        self.vms[vm_name].stop(shutdown_timeout)

    def _restart(self, vm_name):
        vm = self._vm_from_name(vm_name)
        self.vms[vm_name].restart(vm_data=vm, shutdown_timeout=vm['shutdown_timeout'])

    def _status(self, vm_name):
        return self.vms[vm_name].status()
