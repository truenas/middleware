import contextlib
import itertools
import libvirt
import os
import sys
import threading
import time
from xml.etree import ElementTree as etree

from middlewared.service import CallError
from middlewared.plugins.vm.connection import LibvirtConnectionMixin
from middlewared.plugins.vm.devices import CDROM, DISK, NIC, PCI, RAW, DISPLAY, USB # noqa
from middlewared.plugins.vm.utils import ACTIVE_STATES

from .domain_xml import domain_children
from .utils import create_element, DomainState


class VMSupervisor(LibvirtConnectionMixin):

    def __init__(self, vm_data, middleware=None):
        self.vm_data = vm_data
        self.middleware = middleware
        self.devices = []

        self._check_setup_connection()

        self.libvirt_domain_name = f'{self.vm_data["id"]}_{self.vm_data["name"]}'
        self._domain = self.stop_devices_thread = None
        self.update_domain()

    @property
    def domain(self):
        return self.domain_health_check()

    def domain_health_check(self):
        try:
            self._domain.state()
        except (AttributeError, libvirt.libvirtError):
            self.update_domain(update_devices=False)
        return self._domain

    def update_domain(self, vm_data=None, update_devices=True):
        # This can be called to update domain to reflect any changes introduced to the VM
        if update_devices:
            self.update_vm_data(vm_data)
        try:
            self._domain = self.LIBVIRT_CONNECTION.lookupByName(self.libvirt_domain_name)
        except libvirt.libvirtError:
            self._domain = None
        else:
            if not self._domain.isActive():
                # We have a domain defined and it is not running
                self.undefine_domain(for_update=True)

        if not self._domain:
            # This ensures that when a domain has been renamed, we undefine the previous domain name - if object
            # persists in this case of VMSupervisor - else it's the users responsibility to take care of this case
            new_name = f'{self.vm_data["id"]}_{self.vm_data["name"]}'
            if new_name != self.libvirt_domain_name:
                old_nvram_filename = f'/var/lib/libvirt/qemu/nvram/{self.libvirt_domain_name}_VARS.fd'
                with contextlib.suppress(FileNotFoundError):
                    os.rename(old_nvram_filename,
                              f'/var/lib/libvirt/qemu/nvram/{new_name}_VARS.fd')
                self.libvirt_domain_name = new_name
            self.__define_domain()

    def status(self):
        domain = self.domain
        domain_state = DomainState(domain.state()[0])
        pid_path = os.path.join('/var/run/libvirt', 'qemu', f'{self.libvirt_domain_name}.pid')
        if domain.isActive():
            state = 'SUSPENDED' if domain_state == DomainState.PAUSED else 'RUNNING'
        else:
            state = 'STOPPED'

        data = {
            'state': state,
            'pid': None,
            'domain_state': domain_state.name,
        }
        if domain_state in (DomainState.PAUSED, DomainState.RUNNING):
            with contextlib.suppress(FileNotFoundError):
                # Do not make a stat call to check if file exists or not
                with open(pid_path, 'r') as f:
                    data['pid'] = int(f.read())

        return data

    def memory_usage(self):
        # We return this in bytes
        return self.domain.memoryStats().get('actual', 0) * 1024

    def __define_domain(self):
        if self._domain:
            raise CallError(f'{self.libvirt_domain_name} domain has already been defined')

        vm_xml = etree.tostring(self.construct_xml()).decode()
        if not self.LIBVIRT_CONNECTION.defineXML(vm_xml):
            raise CallError(f'Unable to define persistent domain for {self.libvirt_domain_name}')

        self._domain = self.LIBVIRT_CONNECTION.lookupByName(self.libvirt_domain_name)

    def undefine_domain(self, for_update=False):
        if self._domain.isActive():
            raise CallError(f'Domain {self.libvirt_domain_name} is active. Please stop it first')

        flags = 0

        if for_update:
            flags |= libvirt.VIR_DOMAIN_UNDEFINE_KEEP_NVRAM
        else:
            flags |= libvirt.VIR_DOMAIN_UNDEFINE_NVRAM

        self._domain.undefineFlags(flags)
        self._domain = None

    def __getattribute__(self, item):
        retrieved_item = object.__getattribute__(self, item)
        if callable(retrieved_item) and item in ('start', 'stop', 'poweroff', 'undefine_domain', 'status'):
            self.domain_health_check()
            if not getattr(self, '_domain', None):
                raise RuntimeError('Domain attribute not defined, please re-instantiate the VM class')

        return retrieved_item

    def update_vm_data(self, vm_data=None):
        self.vm_data = vm_data or self.vm_data
        self.devices = [
            getattr(sys.modules[__name__], device['attributes']['dtype'])(device, self.middleware)
            for device in sorted(self.vm_data['devices'], key=lambda x: (x['order'], x['id']))
        ]

    def unavailable_devices(self):
        return [d for d in self.devices if not d.is_available()]

    def vm_devices_context(self):
        return {
            'vms': self.middleware.call_sync('vm.query'),
            'vm_devices': self.middleware.call_sync('vm.device.query'),
        }

    def start(self, vm_data=None):
        if self.domain.isActive():
            raise CallError(f'{self.libvirt_domain_name} domain is already active')

        self.update_vm_data(vm_data)

        errors = []
        context = self.vm_devices_context()
        for device in self.devices:
            try:
                device.pre_start_vm_device_setup(context)
            except Exception as e:
                errors.append(str(e))
        if errors:
            errors = '\n'.join(errors)
            raise CallError(f'Failed setting up devices before VM start:\n{errors}')

        unavailable_devices = self.unavailable_devices()
        if unavailable_devices:
            raise CallError(
                f'VM will not start as {", ".join([str(d) for d in unavailable_devices])} device(s) are not available.'
            )

        successful = []
        errors = []
        for device in self.devices:
            try:
                device.pre_start_vm()
            except Exception as e:
                device_dtype = device.data['attributes']['dtype']
                errors.append(f'Failed to setup {device_dtype} device: {e}')
                for d in itertools.chain([device], successful):
                    try:
                        d.pre_start_vm_rollback()
                    except Exception as d_error:
                        d_dtype = d.data['attributes']['dtype']
                        errors.append(
                            f'Failed to rollback pre start changes for {d_dtype} device: {d_error}'
                        )
                break
            else:
                successful.append(device)

        if errors:
            raise CallError('\n'.join(errors))

        try:
            self.update_domain(vm_data, update_devices=False)
            if self.domain.create() < 0:
                raise CallError(f'Failed to boot {self.vm_data["name"]} domain')
        except (libvirt.libvirtError, CallError) as e:
            errors = [str(e)]
            for device in self.devices:
                try:
                    device.pre_start_vm_rollback()
                except Exception as d_error:
                    device_dtype = device.data['attributes']['dtype']
                    errors.append(f'Failed to rollback pre start changes for {device_dtype} device: {d_error}')
            raise CallError('\n'.join(errors))

        # We initialize this when we are certain that the VM has indeed booted
        self.stop_devices_thread = threading.Thread(
            name=f'post_stop_devices_{self.libvirt_domain_name}', target=self.run_post_stop_actions
        )
        self.stop_devices_thread.start()

        errors = []
        for device in self.devices:
            try:
                device.post_start_vm()
            except Exception as e:
                device_dtype = device.data['attributes']['dtype']
                errors.append(f'Failed to execute post start actions for {device_dtype} device: {e}')
        else:
            if errors:
                raise CallError('\n'.join(errors))

    def _before_stopping_checks(self):
        if not self.domain.isActive():
            raise CallError(f'{self.libvirt_domain_name} domain is not active')

    def run_post_stop_actions(self):
        while self.status()['state'] in ACTIVE_STATES:
            time.sleep(5)

        errors = []
        context = self.vm_devices_context()
        for device in self.devices:
            try:
                device.post_stop_vm(context)
            except Exception as e:
                device_dtype = device.data['attributes']['dtype']
                errors.append(f'Failed to execute post stop actions for {device_dtype} device: {e}')
        else:
            if errors:
                raise CallError('\n'.join(errors))

    def stop(self, shutdown_timeout=None):
        self._before_stopping_checks()

        self.domain.shutdown()

        shutdown_timeout = shutdown_timeout or self.vm_data['shutdown_timeout']
        # We wait for timeout seconds before initiating post stop activities for the vm
        # This is done because the shutdown call above is non-blocking
        while shutdown_timeout > 0 and self.status()['state'] == 'RUNNING':
            shutdown_timeout -= 5
            time.sleep(5)

    def poweroff(self):
        self._before_stopping_checks()
        self.domain.destroy()

    def suspend(self):
        self._before_stopping_checks()
        self.domain.suspend()

    def _before_resuming_checks(self):
        if self.status()['state'] != 'SUSPENDED':
            raise CallError(f'{self.libvirt_domain_name!r} domain is not paused')

    def resume(self):
        self._before_resuming_checks()
        self.domain.resume()

    def get_domain_children(self):
        context = {
            'cpu_model_choices': self.middleware.call_sync('vm.cpu_model_choices'),
            'devices': self.devices,
        }
        return domain_children(self.vm_data, context)

    def construct_xml(self):
        return create_element(
            'domain', type='kvm', id=str(self.vm_data['id']), attribute_dict={'children': self.get_domain_children()}
        )
