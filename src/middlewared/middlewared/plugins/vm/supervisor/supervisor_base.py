import contextlib
import enum
import itertools
import libvirt
import os
import shutil
import sys
import threading
import time
from xml.etree import ElementTree as etree

from middlewared.service import CallError
from middlewared.plugins.vm.connection import LibvirtConnectionMixin
from middlewared.plugins.vm.devices import CDROM, DISK, NIC, PCI, RAW, DISPLAY # noqa
from middlewared.utils import osc

from .utils import create_element


class DomainState(enum.Enum):
    NOSTATE = libvirt.VIR_DOMAIN_NOSTATE
    RUNNING = libvirt.VIR_DOMAIN_RUNNING
    BLOCKED = libvirt.VIR_DOMAIN_BLOCKED
    PAUSED = libvirt.VIR_DOMAIN_PAUSED
    SHUTDOWN = libvirt.VIR_DOMAIN_SHUTDOWN
    SHUTOFF = libvirt.VIR_DOMAIN_SHUTOFF
    CRASHED = libvirt.VIR_DOMAIN_CRASHED
    PMSUSPENDED = libvirt.VIR_DOMAIN_PMSUSPENDED


class VMSupervisorBase(LibvirtConnectionMixin):

    def __init__(self, vm_data, middleware=None):
        self.vm_data = vm_data
        self.middleware = middleware
        self.devices = []

        self._check_setup_connection()

        self.libvirt_domain_name = f'{self.vm_data["id"]}_{self.vm_data["name"]}'
        self.domain = self.stop_devices_thread = None
        self.update_domain()

    def update_domain(self, vm_data=None, update_devices=True):
        # This can be called to update domain to reflect any changes introduced to the VM
        if update_devices:
            self.update_vm_data(vm_data)
        try:
            self.domain = self.LIBVIRT_CONNECTION.lookupByName(self.libvirt_domain_name)
        except libvirt.libvirtError:
            self.domain = None
        else:
            if not self.domain.isActive():
                # We have a domain defined and it is not running
                self.undefine_domain()

        if not self.domain:
            # This ensures that when a domain has been renamed, we undefine the previous domain name - if object
            # persists in this case of VMSupervisor - else it's the users responsibility to take care of this case
            self.libvirt_domain_name = f'{self.vm_data["id"]}_{self.vm_data["name"]}'
            self.__define_domain()

    def status(self):
        domain = self.domain
        domain_state = DomainState(domain.state()[0])
        pid_path = os.path.join(
            '/var/run/libvirt', 'qemu' if osc.IS_LINUX else 'bhyve', f'{self.libvirt_domain_name}.pid'
        )
        data = {
            'state': 'STOPPED' if not domain.isActive() else 'RUNNING',
            'pid': None,
            'domain_state': domain_state.name,
        }
        if domain_state == DomainState.RUNNING and os.path.exists(pid_path):
            with open(pid_path, 'r') as f:
                data['pid'] = int(f.read())

        return data

    def __define_domain(self):
        if self.domain:
            raise CallError(f'{self.libvirt_domain_name} domain has already been defined')

        vm_xml = etree.tostring(self.construct_xml()).decode()
        if not self.LIBVIRT_CONNECTION.defineXML(vm_xml):
            raise CallError(f'Unable to define persistent domain for {self.libvirt_domain_name}')

        self.domain = self.LIBVIRT_CONNECTION.lookupByName(self.libvirt_domain_name)

    def undefine_domain(self):
        if self.domain.isActive():
            raise CallError(f'Domain {self.libvirt_domain_name} is active. Please stop it first')

        if self.vm_data['bootloader'] == 'GRUB':
            shutil.rmtree(
                os.path.join('/tmp/grub', self.libvirt_domain_name), ignore_errors=True
            )
        elif osc.IS_LINUX:
            with contextlib.suppress(OSError):
                os.unlink(f'/var/lib/libvirt/qemu/nvram/{self.libvirt_domain_name}_VARS.fd')

        self.domain.undefine()
        self.domain = None

    def __getattribute__(self, item):
        retrieved_item = object.__getattribute__(self, item)
        if callable(retrieved_item) and item in ('start', 'stop', 'restart', 'poweroff', 'undefine_domain', 'status'):
            if not getattr(self, 'domain', None):
                raise RuntimeError('Domain attribute not defined, please re-instantiate the VM class')

        return retrieved_item

    def update_vm_data(self, vm_data=None):
        self.vm_data = vm_data or self.vm_data
        self.devices = [
            getattr(sys.modules[__name__], device['dtype'])(device, self.middleware)
            for device in sorted(self.vm_data['devices'], key=lambda x: (x['order'], x['id']))
        ]

    def unavailable_devices(self):
        return [d for d in self.devices if not d.is_available()]

    def start(self, vm_data=None):
        if self.domain.isActive():
            raise CallError(f'{self.libvirt_domain_name} domain is already active')

        self.update_vm_data(vm_data)

        errors = []
        for device in self.devices:
            try:
                device.pre_start_vm_device_setup()
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

        self.before_start_checks()

        successful = []
        errors = []
        for device in self.devices:
            try:
                device.pre_start_vm()
            except Exception as e:
                errors.append(f'Failed to setup {device.data["dtype"]} device: {e}')
                for d in itertools.chain([device], successful):
                    try:
                        d.pre_start_vm_rollback()
                    except Exception as d_error:
                        errors.append(
                            f'Failed to rollback pre start changes for {d.data["dtype"]} device: {d_error}'
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
                    errors.append(f'Failed to rollback pre start changes for {device.data["dtype"]} device: {d_error}')
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
                errors.append(f'Failed to execute post start actions for {device.data["dtype"]} device: {e}')
        else:
            if errors:
                raise CallError('\n'.join(errors))

    def _before_stopping_checks(self):
        if not self.domain.isActive():
            raise CallError(f'{self.libvirt_domain_name} domain is not active')

    def run_post_stop_actions(self):
        while self.status()['state'] == 'RUNNING':
            time.sleep(5)

        errors = []
        for device in self.devices:
            try:
                device.post_stop_vm()
            except Exception as e:
                errors.append(f'Failed to execute post stop actions for {device.data["dtype"]} device: {e}')
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

    def restart(self, vm_data=None, shutdown_timeout=None):
        self.stop(shutdown_timeout)

        # We don't wait anymore because during stop we have already waited for the VM to shutdown cleanly
        if self.status()['state'] == 'RUNNING':
            # In case domain stopped between this time
            with contextlib.suppress(libvirt.libvirtError):
                self.poweroff()

        self.start(vm_data)

    def poweroff(self):
        self._before_stopping_checks()
        self.domain.destroy()

    def get_domain_children(self):
        domain_children = [
            create_element('name', attribute_dict={'text': self.libvirt_domain_name}),
            create_element('title', attribute_dict={'text': self.vm_data['name']}),
            create_element('description', attribute_dict={'text': self.vm_data['description']}),
            # OS/boot related xml - returns an iterable
            *self.os_xml(),
            # VCPU related xml
            create_element('vcpu', attribute_dict={
                'text': str(self.vm_data['vcpus'] * self.vm_data['cores'] * self.vm_data['threads'])
            }),
            self.cpu_xml(),
            # Memory related xml
            create_element('memory', unit='M', attribute_dict={'text': str(self.vm_data['memory'])}),
            # Add features
            self.get_features_xml(),
            # Clock offset
            create_element('clock', offset='localtime' if self.vm_data['time'] == 'LOCAL' else 'utc'),
            # Devices
            self.devices_xml(),
            # Command line args
            *self.commandline_xml(),
        ]

        # Wire memory if PCI passthru device is configured
        #   Implicit configuration for now.
        #
        #   To avoid surprising side effects from implicit configuration, wiring of memory
        #   should preferably be an explicit vm configuration option and trigger error
        #   message if not selected when PCI passthru is configured.
        #
        if any(isinstance(device, PCI) for device in self.devices):
            domain_children.append(
                create_element(
                    'memoryBacking', attribute_dict={
                        'children': [
                            create_element('locked'),
                        ]
                    }
                )
            )

        return domain_children

    def get_features_xml(self):
        features = []
        if self.vm_data['hide_from_msr']:
            features.append(
                create_element('kvm', attribute_dict={'children': [create_element('hidden', state='on')]})
            )
        return create_element(
            'features', attribute_dict={
                'children': [
                    create_element('acpi'),
                    create_element('msrs', unknown='ignore'),
                ] + features,
            }
        )

    def before_start_checks(self):
        # Let's ensure that we are able to boot a GRUB based VM
        if self.vm_data['bootloader'] == 'GRUB':
            if not any(
                isinstance(d, RAW) and d.data['attributes'].get('boot') for d in self.devices
            ):
                raise CallError(f'Unable to find boot devices for {self.libvirt_domain_name!r} domain')
            grub_config = (self.vm_data['grubconfig'] or '').strip()
            if grub_config.startswith('/mnt') and not os.path.exists(grub_config):
                raise CallError(
                    f'Unable to locate {grub_config!r} grubconfig path for {self.libvirt_domain_name!r} domain'
                )

    def cpu_xml(self):
        return create_element(
            'cpu', attribute_dict={
                'children': [
                    create_element(
                        'topology', sockets=str(self.vm_data['vcpus']), cores=str(self.vm_data['cores']),
                        threads=str(self.vm_data['threads'])
                    )
                ]
            }
        )

    def construct_xml(self):
        raise NotImplementedError

    def commandline_xml(self):
        raise NotImplementedError

    def os_xml(self):
        raise NotImplementedError

    def devices_xml(self):
        raise NotImplementedError
