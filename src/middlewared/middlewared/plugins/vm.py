from middlewared.async_validators import check_path_resides_within_volume
from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.schema import accepts, Error, Int, Str, Dict, List, Bool, Patch
from middlewared.service import (
    item_method, pass_app, private, CRUDService, CallError, ValidationErrors, job
)
import middlewared.sqlalchemy as sa
from middlewared.utils import Nid, osc, Popen, run
from middlewared.utils.asyncio_ import asyncio_map
from middlewared.utils.path import is_child
from middlewared.validators import Range, Match

import middlewared.logger
import asyncio
import contextlib
import errno
import enum
import functools
import ipaddress
import itertools
import libvirt
import math
try:
    import netif
except ImportError:
    netif = None
import os
import psutil
import random
import re
import stat
import shutil
import signal
import subprocess
import sys
try:
    import sysctl
except ImportError:
    sysctl = None
import time
import threading

from abc import ABC, abstractmethod
from lxml import etree

logger = middlewared.logger.Logger('vm').getLogger()

BUFSIZE = 65536

LIBVIRT_URI = 'bhyve+unix:///system'
LIBVIRT_AVAILABLE_SLOTS = 29  # 3 slots are being used by libvirt / bhyve
LIBVIRT_BHYVE_NAMESPACE = 'http://libvirt.org/schemas/domain/bhyve/1.0'
LIBVIRT_BHYVE_NSMAP = {'bhyve': LIBVIRT_BHYVE_NAMESPACE}
LIBVIRT_LOCK = asyncio.Lock()


ZVOL_CLONE_SUFFIX = '_clone'
ZVOL_CLONE_RE = re.compile(rf'^(.*){ZVOL_CLONE_SUFFIX}\d+$')


def create_element(*args, **kwargs):
    attribute_dict = kwargs.pop('attribute_dict', {})
    element = etree.Element(*args, **kwargs)
    element.text = attribute_dict.get('text')
    element.tail = attribute_dict.get('tail')
    for child in attribute_dict.get('children', []):
        element.append(child)
    return element


class DomainState(enum.Enum):
    NOSTATE = libvirt.VIR_DOMAIN_NOSTATE
    RUNNING = libvirt.VIR_DOMAIN_RUNNING
    BLOCKED = libvirt.VIR_DOMAIN_BLOCKED
    PAUSED = libvirt.VIR_DOMAIN_PAUSED
    SHUTDOWN = libvirt.VIR_DOMAIN_SHUTDOWN
    SHUTOFF = libvirt.VIR_DOMAIN_SHUTOFF
    CRASHED = libvirt.VIR_DOMAIN_CRASHED
    PMSUSPENDED = libvirt.VIR_DOMAIN_PMSUSPENDED


class VMSupervisor:

    def __init__(self, vm_data, connection, middleware=None):
        self.vm_data = vm_data
        self.connection = connection
        self.middleware = middleware
        self.devices = []

        if not self.connection or not self.connection.isAlive():
            raise CallError(f'Failed to connect to libvirtd for {self.vm_data["name"]}')

        self.libvirt_domain_name = f'{self.vm_data["id"]}_{self.vm_data["name"]}'
        self.domain = self.stop_devices_thread = None
        self.update_domain()

    def update_domain(self, vm_data=None, update_devices=True):
        # This can be called to update domain to reflect any changes introduced to the VM
        if update_devices:
            self.update_vm_data(vm_data)
        try:
            self.domain = self.connection.lookupByName(self.libvirt_domain_name)
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
        return {
            'state': 'STOPPED' if not domain.isActive() else 'RUNNING',
            'pid': None if not domain.isActive() else self.domain.ID(),
            'domain_state': DomainState(domain.state()[0]).name,
        }

    def __define_domain(self):
        if self.domain:
            raise CallError(f'{self.libvirt_domain_name} domain has already been defined')

        vm_xml = etree.tostring(self.construct_xml()).decode()
        if not self.connection.defineXML(vm_xml):
            raise CallError(f'Unable to define persistent domain for {self.libvirt_domain_name}')

        self.domain = self.connection.lookupByName(self.libvirt_domain_name)

    def undefine_domain(self):
        if self.domain.isActive():
            raise CallError(f'Domain {self.libvirt_domain_name} is active. Please stop it first')

        if self.vm_data['bootloader'] == 'GRUB':
            shutil.rmtree(
                os.path.join('/tmp/grub', self.libvirt_domain_name), ignore_errors=True
            )

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

    def start(self, vm_data=None):
        if self.domain.isActive():
            raise CallError(f'{self.libvirt_domain_name} domain is already active')

        self.update_vm_data(vm_data)

        # Let's ensure that we are able to boot a GRUB based VM
        if self.vm_data['bootloader'] == 'GRUB' and not any(
            isinstance(d, RAW) and d.data['attributes'].get('boot') for d in self.devices
        ):
            raise CallError(f'Unable to find boot devices for {self.libvirt_domain_name} domain')

        if len([d for d in self.devices if isinstance(d, VNC)]) > 1:
            raise CallError('Only one VNC device per VM is supported')

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

    def guest_pptdev(self, ppt_maps, nid, host_bsf):

        # Multi-function PCI devices are not always independent. For some (but
        # not all) adapters the mappings of functions must be the same in the
        # guest. For simplicity, we map functions of the same host slot on one
        # guest slot.

        # Compile list of already assigned devices with same source slot
        mylist = (item for item in ppt_maps if item['host_bsf'][0:2] == host_bsf[0:2])
        item = next(mylist, None)
        if item is None:
            # Source bus/slot not seen before. Map on new guest slot.
            guest_slot = nid()
        else:
            # Source bus/slot seen before. Reuse the old guest slot.
            guest_slot = item['guest_bsf'][1]
            # Check if the function has already been mapped.
            # No need to map the same bus/slot/function more than once.
            while (item is not None and item['host_bsf'] != host_bsf):
                # Not same function. Check next item.
                item = next(mylist, None)
        if item is None:
            # This host bus/slot/function is not mapped yet.
            # Add passthru device
            guest_bsf = [0, guest_slot, host_bsf[2]]
            return guest_bsf
        return None

    def construct_xml(self):
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
            create_element(
                'cpu', attribute_dict={
                    'children': [
                        create_element(
                            'topology', sockets=str(self.vm_data['vcpus']), cores=str(self.vm_data['cores']),
                            threads=str(self.vm_data['threads'])
                        )
                    ]
                }
            ),
            # Memory related xml
            create_element('memory', unit='M', attribute_dict={'text': str(self.vm_data['memory'])}),
            # Add features
            create_element(
                'features', attribute_dict={
                    'children': [
                        create_element('acpi'),
                        create_element('msrs', unknown='ignore'),
                    ]
                }
            ),
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

        return create_element(
            'domain', type='bhyve', id=str(self.vm_data['id']),
            attribute_dict={'children': domain_children}, nsmap=LIBVIRT_BHYVE_NSMAP,
        )

    def commandline_xml(self):
        commandline_args = self.commandline_args()
        return [create_element(
            etree.QName(LIBVIRT_BHYVE_NAMESPACE, 'commandline'), attribute_dict={
                'children': [
                    create_element(
                        etree.QName(LIBVIRT_BHYVE_NAMESPACE, 'arg'),
                        value=cmd_arg, nsmap=LIBVIRT_BHYVE_NSMAP
                    ) for cmd_arg in commandline_args
                ]
            }
        )] if commandline_args else []

    def commandline_args(self):
        args = []
        for device in filter(lambda d: isinstance(d, (PCI, VNC)), self.devices):
            args += filter(None, [device.bhyve_args()])
        return args

    def os_xml(self):
        os_list = []
        children = [create_element('type', attribute_dict={'text': 'hvm'})]
        if self.vm_data['bootloader'] in ('UEFI', 'UEFI_CSM'):
            children.append(
                create_element(
                    'loader', attribute_dict={
                        'text': '/usr/local/share/uefi-firmware/BHYVE_UEFI'
                        f'{"_CSM" if self.vm_data["bootloader"] == "UEFI_CSM" else ""}.fd'
                    }, readonly='yes', type='pflash',
                ),
            )

        if self.vm_data['bootloader'] == 'GRUB':
            # Following is keeping compatibility with old code where we supported rancher/docker
            # We can have two cases where the user has the path set pointing to his/her grub file or where
            # the data inside grubconfig is saved and we write out a new file for it
            # In either of these cases we require device map file to be written

            device_map_data = '\n'.join(
                f'(hd{i}) {d.data["attributes"]["path"]}' for i, d in enumerate(filter(
                    lambda d: isinstance(d, RAW) and d.data['attributes'].get('boot'), self.devices
                ))
            )
            # It will be ensured while starting that this VM is capable of starting i.e has boot devices

            os_list.append(create_element(
                'bootloader', attribute_dict={'text': '/usr/local/sbin/grub-bhyve'}
            ))

            device_map_dir = os.path.join('/tmp/grub', self.libvirt_domain_name)
            device_map_file = os.path.join(device_map_dir, 'devices_map')
            os.makedirs(device_map_dir, exist_ok=True)

            with open(device_map_file, 'w') as f:
                f.write(device_map_data)

            if self.vm_data['grubconfig']:
                grub_config = self.vm_data['grubconfig'].strip()
                if grub_config.startswith('/mnt') and os.path.exists(grub_config):
                    grub_dir = os.path.dirname(grub_config)
                else:
                    grub_dir = device_map_dir
                    with open(os.path.join(grub_dir, 'grub.cfg'), 'w') as f:
                        f.write(grub_config)

                os_list.append(create_element(
                    'bootloader_args', attribute_dict={
                        'text': ' '.join([
                            '-m', device_map_file, '-r', 'host', '-M', str(self.vm_data['memory']),
                            '-d', grub_dir, self.libvirt_domain_name
                        ])
                    }
                ))

        os_list.append(create_element('os', attribute_dict={'children': children}))

        return os_list

    def devices_xml(self):
        devices = []
        pci_slot = Nid(3)
        controller_index = Nid(1)
        controller_base = {'index': None, 'slot': None, 'function': 0, 'devices': 0}
        ahci_current_controller = controller_base.copy()
        virtio_current_controller = controller_base.copy()
        ppt_maps = []

        for device in self.devices:
            if isinstance(device, (DISK, CDROM, RAW)):
                # We classify all devices in 2 types:
                # 1) AHCI
                # 2) VIRTIO
                # Before deciding how we attach the disk/cdrom devices wrt slots/functions, following are few basic
                # rules:
                # We have a maximum of 32 slots ( 0-31 ) available which can be attached to the VM. Each slot supports
                # functions which for each slot can be up to 8 ( 0-7 ). For legacy reasons, we start with the 3rd
                # slot for numbering disks.

                # AHCI based devices can be up to 32 in number per function.
                # VIRTIO based disk devices consume a complete function meaning a maximum of 1 VIRTIO device can be
                # present in a function.

                # Libvirt / freebsd specific implementation
                # We do not have great support of bhyve driver in libvirt, so this is a best effort to emulate our
                # old implementation command. Following are a few points i have outlined to make the following logic
                # clearer:
                # 1) For AHCI based devices, libvirt assigns all of them to one slot ( a bug there ), we don't want
                # that of course as bhyve imposes a restriction of a maximum 32 devices per function for AHCI. To come
                # around this issue, controllers have been used for AHCI based devices which help us manage them
                # nicely allotting them on specific supplied slots/functions.
                # 2) For VIRTIO based disk devices, we use "pci" for their address type which helps us set
                # the slot/function number and it actually being respected. Reason this can't be used with AHCI is
                # that pci and sata bus are incompatible in AHCI and libvirt raises an error in this case.

                if device.data['attributes'].get('type') != 'VIRTIO':
                    virtio = False
                    current_controller = ahci_current_controller
                    max_devices = 32
                else:
                    virtio = True
                    current_controller = virtio_current_controller
                    max_devices = 1

                if not current_controller['slot'] or current_controller['devices'] == max_devices:
                    # Two scenarios will happen, either we bump function no or slot no
                    if not current_controller['slot'] or current_controller['function'] == 8:
                        # We need to add a new controller with a new slot
                        current_controller.update({
                            'slot': pci_slot(),
                            'function': 0,
                            'devices': 0,
                        })
                    else:
                        # We just need to bump the function here
                        current_controller.update({
                            'function': current_controller['function'] + 1,
                            'devices': 0,
                        })

                    # We should add this to xml now
                    if not virtio:
                        current_controller['index'] = controller_index()
                        devices.append(create_element(
                            'controller', type='sata', index=str(current_controller['index']), attribute_dict={
                                'children': [
                                    create_element(
                                        'address', type='pci', slot=str(current_controller['slot']),
                                        function=str(current_controller['function']), multifunction='on'
                                    )
                                ]
                            }
                        ))

                current_controller['devices'] += 1

                if virtio:
                    address_dict = {
                        'type': 'pci', 'slot': str(current_controller['slot']),
                        'function': str(current_controller['function'])
                    }
                else:
                    address_dict = {
                        'type': 'drive', 'controller': str(current_controller['index']),
                        'target': str(current_controller['devices'])
                    }

                device_xml = device.xml(child_element=create_element('address', **address_dict))
            elif isinstance(device, NIC):
                device_xml = device.xml(slot=pci_slot())
            elif isinstance(device, PCI):
                # PCI passthru section begins here
                # Check if ppt device is available for passthru. Map, only if available.
                host_bsf = device.ppt_map['host_bsf']
                if host_bsf is not None:
                    guest_bsf = self.guest_pptdev(ppt_maps, pci_slot, host_bsf)
                else:
                    guest_bsf = None
                device.ppt_map['guest_bsf'] = guest_bsf
                if guest_bsf is not None:
                    ppt_maps.append(device.ppt_map)
                device_xml = device.xml()
                # PCI passthru section ends here
            else:
                device_xml = device.xml()

            if device_xml is not None:
                devices.extend(device_xml if isinstance(device_xml, (tuple, list)) else [device_xml])

        devices.append(
            create_element(
                'serial', type='nmdm', attribute_dict={
                    'children': [
                        create_element(
                            'source', master=f'/dev/nmdm{self.vm_data["id"]}A', slave=f'/dev/nmdm{self.vm_data["id"]}B'
                        )
                    ]
                }
            )
        )

        return create_element('devices', attribute_dict={'children': devices})


class VMModel(sa.Model):
    __tablename__ = 'vm_vm'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(150))
    description = sa.Column(sa.String(250))
    vcpus = sa.Column(sa.Integer(), default=1)
    memory = sa.Column(sa.Integer())
    autostart = sa.Column(sa.Boolean(), default=False)
    time = sa.Column(sa.String(5), default='LOCAL')
    grubconfig = sa.Column(sa.Text(), nullable=True)
    bootloader = sa.Column(sa.String(50), default='UEFI')
    cores = sa.Column(sa.Integer(), default=1)
    threads = sa.Column(sa.Integer(), default=1)
    shutdown_timeout = sa.Column(sa.Integer(), default=90)


class VMService(CRUDService):

    class Config:
        namespace = 'vm'
        datastore = 'vm.vm'
        datastore_extend = 'vm.extend_vm'

    def __init__(self, *args, **kwargs):
        super(VMService, self).__init__(*args, **kwargs)
        self.vms = {}
        self.libvirt_connection = None

    @accepts()
    def flags(self):
        """Returns a dictionary with CPU flags for bhyve."""
        data = {}
        intel = True if 'Intel' in sysctl.filter('hw.model')[0].value else \
            False

        vmx = sysctl.filter('hw.vmm.vmx.initialized')
        data['intel_vmx'] = True if vmx and vmx[0].value else False

        ug = sysctl.filter('hw.vmm.vmx.cap.unrestricted_guest')
        data['unrestricted_guest'] = True if ug and ug[0].value else False

        # If virtualisation is not supported on AMD, the sysctl value will be -1 but as an unsigned integer
        # we should make sure we check that accordingly.
        rvi = sysctl.filter('hw.vmm.svm.features')
        data['amd_rvi'] = True if rvi and rvi[0].value != 0xffffffff and not intel \
            else False

        asids = sysctl.filter('hw.vmm.svm.num_asids')
        data['amd_asids'] = True if asids and asids[0].value != 0 else False

        return data

    @accepts()
    def identify_hypervisor(self):
        """
        Identify Hypervisors that might work nested with bhyve.

        Returns:
                bool: True if compatible otherwise False.
        """
        compatible_hp = ('VMwareVMware', 'Microsoft Hv', 'KVMKVMKVM', 'bhyve bhyve')
        identify_hp = sysctl.filter('hw.hv_vendor')[0].value.strip()

        if identify_hp in compatible_hp:
            return True
        return False

    @private
    async def extend_vm(self, vm):
        vm['devices'] = await self.middleware.call('vm.device.query', [('vm', '=', vm['id'])])
        vm['status'] = await self.middleware.call('vm.status', vm['id'])
        return vm

    @accepts(Int('id'))
    async def get_vnc(self, id):
        """
        Get the vnc devices from a given guest.

        Returns:
            list(dict): with all attributes of the vnc device or an empty list.
        """
        vnc_devices = []
        for device in await self.middleware.call('datastore.query', 'vm.device', [('vm', '=', id)]):
            if device['dtype'] == 'VNC':
                vnc = device['attributes']
                vnc_devices.append(vnc)
        return vnc_devices

    @accepts()
    async def vnc_port_wizard(self):
        """
        It returns the next available VNC PORT and WEB VNC PORT.

        Returns a dict with two keys vnc_port and vnc_web.
        """
        all_ports = [
            d['attributes'].get('vnc_port')
            for d in (await self.middleware.call('vm.device.query', [['dtype', '=', 'VNC']]))
        ] + [6000, 6100]

        vnc_port = next((i for i in range(5900, 65535) if i not in all_ports))
        return {'vnc_port': vnc_port, 'vnc_web': VNC.get_vnc_web_port(vnc_port)}

    @accepts()
    def get_vnc_ipv4(self):
        """
        Get all available IPv4 address in the system.

        Returns:
           list: will return a list of available IPv4 address.
        """
        default_ifaces = ['0.0.0.0', '127.0.0.1']
        ifaces_dict_list = self.middleware.call_sync('interface.ip_in_use', {'ipv6': False})
        ifaces = [alias_dict['address'] for alias_dict in ifaces_dict_list]

        default_ifaces.extend(ifaces)
        return default_ifaces

    @accepts(Int('id'))
    async def get_attached_iface(self, id):
        """
        Get the attached physical interfaces from a given guest.

        Returns:
            list: will return a list with all attached phisycal interfaces or otherwise False.
        """
        ifaces = []
        for device in await self.middleware.call('datastore.query', 'vm.device', [('vm', '=', id)]):
            if device['dtype'] == 'NIC':
                if_attached = device['attributes'].get('nic_attach')
                if if_attached:
                    ifaces.append(if_attached)

        if ifaces:
            return ifaces
        else:
            return False

    @accepts(Int('id'))
    async def get_console(self, id):
        """
        Get the console device from a given guest.

        Returns:
            str: with the device path or False.
        """
        try:
            guest_status = await self.middleware.call('vm.status', id)
        except Exception:
            guest_status = None

        if guest_status and guest_status['state'] == 'RUNNING':
            device = '/dev/nmdm{0}B'.format(id)
            if stat.S_ISCHR(os.stat(device).st_mode) is True:
                return device

        return False

    @accepts()
    async def get_vmemory_in_use(self):
        """
        The total amount of virtual memory in MB used by guests

            Returns a dict with the following information:
                RNP - Running but not provisioned
                PRD - Provisioned but not running
                RPRD - Running and provisioned
        """
        memory_allocation = {'RNP': 0, 'PRD': 0, 'RPRD': 0}
        guests = await self.middleware.call('datastore.query', 'vm.vm')
        for guest in guests:
            status = await self.middleware.call('vm.status', guest['id'])
            if status['state'] == 'RUNNING' and guest['autostart'] is False:
                memory_allocation['RNP'] += guest['memory'] * 1024 * 1024
            elif status['state'] == 'RUNNING' and guest['autostart'] is True:
                memory_allocation['RPRD'] += guest['memory'] * 1024 * 1024
            elif guest['autostart']:
                memory_allocation['PRD'] += guest['memory'] * 1024 * 1024

        return memory_allocation

    @accepts(Bool('overcommit', default=False))
    def get_available_memory(self, overcommit):
        """
        Get the current maximum amount of available memory to be allocated for VMs.

        If `overcommit` is true only the current used memory of running VMs will be accounted for.
        If false all memory (including unused) of runnings VMs will be accounted for.

        This will include memory shrinking ZFS ARC to the minimum.

        Memory is of course a very "volatile" resource, values may change abruptly between a
        second but I deem it good enough to give the user a clue about how much memory is
        available at the current moment and if a VM should be allowed to be launched.
        """
        # Use 90% of available memory to play safe
        free = int(psutil.virtual_memory().available * 0.9)

        # swap used space is accounted for used physical memory because
        # 1. processes (including VMs) can be swapped out
        # 2. we want to avoid using swap
        swap_used = psutil.swap_memory().used * sysctl.filter('hw.pagesize')[0].value

        # Difference between current ARC total size and the minimum allowed
        arc_total = sysctl.filter('kstat.zfs.misc.arcstats.size')[0].value
        arc_min = sysctl.filter('vfs.zfs.arc.min')[0].value
        arc_shrink = max(0, arc_total - arc_min)

        vms_memory_used = 0
        if overcommit is False:
            # If overcommit is not wanted its verified how much physical memory
            # the bhyve process is currently using and add the maximum memory its
            # supposed to have.
            for vm in self.middleware.call_sync('vm.query'):
                status = self.middleware.call_sync('vm.status', vm['id'])
                if status['pid']:
                    try:
                        p = psutil.Process(status['pid'])
                    except psutil.NoSuchProcess:
                        continue
                    memory_info = p.memory_info()._asdict()
                    memory_info.pop('vms')
                    vms_memory_used += (vm['memory'] * 1024 * 1024) - sum(memory_info.values())

        return max(0, free + arc_shrink - vms_memory_used - swap_used)

    async def __set_guest_vmemory(self, memory, overcommit):
        memory_available = await self.middleware.call('vm.get_available_memory', overcommit)
        memory_bytes = memory * 1024 * 1024
        if memory_bytes > memory_available:
            return False

        arc_max = sysctl.filter('vfs.zfs.arc.max')[0].value
        arc_min = sysctl.filter('vfs.zfs.arc.min')[0].value

        if arc_max > arc_min:
            new_arc_max = max(arc_min, arc_max - memory_bytes)
            self.logger.info(
                f'===> Setting ARC FROM: {arc_max} TO: {new_arc_max}'
            )
            sysctl.filter('vfs.zfs.arc.max')[0].value = new_arc_max
        return True

    @private
    async def init_guest_vmemory(self, vm, overcommit):
        guest_memory = vm.get('memory', None)
        guest_status = await self.middleware.call('vm.status', vm['id'])
        if guest_status.get('state') != 'RUNNING':
            setvmem = await self.__set_guest_vmemory(guest_memory, overcommit)
            if setvmem is False and not overcommit:
                raise CallError(f'Cannot guarantee memory for guest {vm["name"]}', errno.ENOMEM)
        else:
            raise CallError('bhyve process is running, we won\'t allocate memory')

    @accepts()
    def random_mac(self):
        """ Create a random mac address.

            Returns:
                str: with six groups of two hexadecimal digits
        """
        return NIC.random_mac()

    @accepts(Dict(
        'vm_create',
        Str('name', required=True),
        Str('description'),
        Int('vcpus', default=1),
        Int('cores', default=1),
        Int('threads', default=1),
        Int('memory', required=True),
        Str('bootloader', enum=['UEFI', 'UEFI_CSM', 'GRUB'], default='UEFI'),
        Str('grubconfig', null=True),
        List('devices', default=[], items=[Patch('vmdevice_create', 'vmdevice_update', ('rm', {'name': 'vm'}))]),
        Bool('autostart', default=True),
        Str('time', enum=['LOCAL', 'UTC'], default='LOCAL'),
        Int('shutdown_timeout', default=90, valdiators=[Range(min=5, max=300)]),
        register=True,
    ))
    async def do_create(self, data):
        """
        Create a Virtual Machine (VM).

        `grubconfig` may either be a path for the grub.cfg file or the actual content
        of the file to be used with GRUB bootloader.

        `devices` is a list of virtualized hardware to add to the newly created Virtual Machine.
        Failure to attach a device destroys the VM and any resources allocated by the VM devices.

        Maximum of 16 guest virtual CPUs are allowed. By default, every virtual CPU is configured as a
        separate package. Multiple cores can be configured per CPU by specifying `cores` attributes.
        `vcpus` specifies total number of CPU sockets. `cores` specifies number of cores per socket. `threads`
        specifies number of threads per core.

        `shutdown_timeout` indicates the time in seconds the system waits for the VM to cleanly shutdown. During system
        shutdown, if the VM hasn't exited after a hardware shutdown signal has been sent by the system within
        `shutdown_timeout` seconds, system initiates poweroff for the VM to stop it.
        """
        async with LIBVIRT_LOCK:
            if not self.libvirt_connection:
                await self.wait_for_libvirtd(10)
        await self.middleware.call('vm.ensure_libvirt_connection')

        verrors = ValidationErrors()
        await self.__common_validation(verrors, 'vm_create', data)
        verrors.check()

        devices = data.pop('devices')
        vm_id = await self.middleware.call('datastore.insert', 'vm.vm', data)
        try:
            await self.safe_devices_updates(devices)
        except Exception as e:
            await self.middleware.call('vm.delete', vm_id)
            raise e
        else:
            for device in devices:
                await self.middleware.call('vm.device.create', {'vm': vm_id, **device})

        await self.middleware.run_in_thread(
            lambda vms, vd, con, mw: vms.update({vd['name']: VMSupervisor(vd, con, mw)}),
            self.vms, (await self.get_instance(vm_id)), self.libvirt_connection, self.middleware
        )

        return await self.get_instance(vm_id)

    @private
    async def safe_devices_updates(self, devices):
        # We will filter devices which create resources and if any of those fail, we destroy the created
        # resources with the devices
        # Returns true if resources were created successfully, false otherwise
        created_resources = []
        existing_devices = {d['id']: d for d in await self.middleware.call('vm.device.query')}
        try:
            for device in devices:
                if not await self.middleware.call(
                    'vm.device.create_resource', device, existing_devices.get(device.get('id'))
                ):
                    continue

                created_resources.append(
                    await self.middleware.call(
                        'vm.device.update_device', device, existing_devices.get(device.get('id'))
                    )
                )
        except Exception as e:
            for created_resource in created_resources:
                try:
                    await self.middleware.call(
                        'vm.device.delete_resource', {
                            'zvol': created_resource['dtype'] == 'DISK', 'raw_file': created_resource['dtype'] == 'RAW'
                        }, created_resource
                    )
                except Exception as e:
                    self.logger.warn(f'Failed to delete {created_resource["dtype"]}: {e}', exc_info=True)
            raise e

    async def __common_validation(self, verrors, schema_name, data, old=None):

        vcpus = data['vcpus'] * data['cores'] * data['threads']
        if vcpus:
            flags = await self.middleware.call('vm.flags')
            if vcpus > 16:
                verrors.add(
                    f'{schema_name}.vcpus',
                    'Maximum 16 vcpus are supported.'
                    f'Please ensure the product of "{schema_name}.vcpus", "{schema_name}.cores" and '
                    f'"{schema_name}.threads" is less then 16.'
                )
            elif flags['intel_vmx']:
                if vcpus > 1 and flags['unrestricted_guest'] is False:
                    verrors.add(
                        f'{schema_name}.vcpus',
                        'Only one Virtual CPU is allowed in this system.',
                    )
            elif flags['amd_rvi']:
                if vcpus > 1 and flags['amd_asids'] is False:
                    verrors.add(
                        f'{schema_name}.vcpus',
                        'Only one virtual CPU is allowed in this system.',
                    )
            elif not flags['intel_vmx'] and not flags['amd_rvi']:
                verrors.add(
                    schema_name,
                    'This system does not support virtualization.'
                )

        if 'name' in data:
            filters = [('name', '=', data['name'])]
            if old:
                filters.append(('id', '!=', old['id']))
            if await self.middleware.call('vm.query', filters):
                verrors.add(f'{schema_name}.name', 'This name already exists.', errno.EEXIST)
            elif not re.search(r'^[a-zA-Z_0-9]+$', data['name']):
                verrors.add(f'{schema_name}.name', 'Only alphanumeric characters are allowed.')

        devices_ids = {d['id']: d for d in await self.middleware.call('vm.device.query')}
        for i, device in enumerate(data.get('devices') or []):
            try:
                await self.middleware.call(
                    'vm.device.validate_device', device, devices_ids.get(device.get('id')), data
                )
                if old:
                    # We would like to enforce the presence of "vm" attribute in each device so that
                    # it explicitly tells it wants to be associated to the provided "vm" in question
                    if device.get('id') and device['id'] not in devices_ids:
                        verrors.add(
                            f'{schema_name}.devices.{i}.{device["id"]}',
                            f'VM device {device["id"]} does not exist.'
                        )
                    elif not device.get('vm') or device['vm'] != old['id']:
                        verrors.add(
                            f'{schema_name}.devices.{i}.{device["id"]}',
                            f'Device must be associated with current VM {old["id"]}.'
                        )
            except ValidationErrors as verrs:
                for attribute, errmsg, enumber in verrs:
                    verrors.add(f'{schema_name}.devices.{i}.{attribute}', errmsg, enumber)

        # Let's validate that the VM has the correct no of slots available to accommodate currently configured devices
        if self.validate_slots(data):
            verrors.add(
                f'{schema_name}.devices',
                'Please adjust the devices attached to this VM. A maximum of 30 PCI slots are allowed.'
            )

    @private
    def validate_slots(self, vm_data):
        # Returns True if their aren't enough slots to support all the devices configured, False otherwise
        virtio_disk_devices = raw_ahci_disk_devices = other_devices = 0
        for device in (vm_data.get('devices') or []):
            if device['dtype'] not in ('DISK', 'RAW'):
                other_devices += 1
            else:
                if device['attributes'].get('type') == 'VIRTIO':
                    virtio_disk_devices += 1
                else:
                    raw_ahci_disk_devices += 1
        used_slots = other_devices
        used_slots += math.ceil(virtio_disk_devices / 8)  # Per slot we can have 8 virtio disks, so we divide it by 8
        # Per slot we can have 256 disks.
        used_slots += math.ceil(raw_ahci_disk_devices / 256)
        return used_slots > LIBVIRT_AVAILABLE_SLOTS  # 3 slots are already in use i.e by libvirt/bhyve

    async def __do_update_devices(self, id, devices):
        # There are 3 cases:
        # 1) "devices" can have new device entries
        # 2) "devices" can have updated existing entries
        # 3) "devices" can have removed exiting entries
        old_devices = await self.middleware.call('vm.device.query', [['vm', '=', id]])
        existing_devices = [d.copy() for d in devices if 'id' in d]
        for remove_id in ({d['id'] for d in old_devices} - {d['id'] for d in existing_devices}):
            await self.middleware.call('vm.device.delete', remove_id)

        for update_device in existing_devices:
            device_id = update_device.pop('id')
            await self.middleware.call('vm.device.update', device_id, update_device)

        for create_device in filter(lambda v: 'id' not in v, devices):
            await self.middleware.call('vm.device.create', create_device)

    @accepts(
        Int('id'),
        Patch(
            'vm_create',
            'vm_update',
            ('attr', {'update': True}),
            (
                'edit', {
                    'name': 'devices', 'method': lambda v: setattr(
                        v, 'items', [Patch(
                            'vmdevice_create', 'vmdevice_update',
                            ('add', {'name': 'id', 'type': 'int', 'required': False})
                        )]
                    )
                }
            )
        )
    )
    async def do_update(self, id, data):
        """
        Update all information of a specific VM.

        `devices` is a list of virtualized hardware to attach to the virtual machine. If `devices` is not present,
        no change is made to devices. If either the device list order or data stored by the device changes when the
        attribute is passed, these actions are taken:

        1) If there is no device in the `devices` list which was previously attached to the VM, that device is
           removed from the virtual machine.
        2) Devices are updated in the `devices` list when they contain a valid `id` attribute that corresponds to
           an existing device.
        3) Devices that do not have an `id` attribute are created and attached to `id` VM.
        """

        old = await self.get_instance(id)
        new = old.copy()
        new.update(data)

        if new['name'] != old['name']:
            await self.middleware.call('vm.ensure_libvirt_connection')
            if old['status']['state'] == 'RUNNING':
                raise CallError('VM name can only be changed when VM is inactive')

            if old['name'] not in self.vms:
                raise CallError(f'Unable to locate domain for {old["name"]}')

        verrors = ValidationErrors()
        await self.__common_validation(verrors, 'vm_update', new, old=old)
        if verrors:
            raise verrors

        devices = new.pop('devices', [])
        new.pop('status', None)
        if devices != old['devices']:
            await self.safe_devices_updates(devices)
            await self.__do_update_devices(id, devices)

        await self.middleware.call('datastore.update', 'vm.vm', id, new)

        vm_data = await self.get_instance(id)
        if new['name'] != old['name']:
            await self.middleware.call('vm.rename_domain', old, vm_data)

        return await self.get_instance(id)

    @private
    def rename_domain(self, old, new):
        vm = self.vms.pop(old['name'])
        vm.update_domain(new)
        self.vms[new['name']] = vm

    @accepts(
        Int('id'),
        Dict(
            'vm_delete',
            Bool('zvols', default=False),
            Bool('force', default=False),
        ),
    )
    async def do_delete(self, id, data):
        """Delete a VM."""
        async with LIBVIRT_LOCK:
            vm = await self.get_instance(id)
            await self.middleware.call('vm.ensure_libvirt_connection')
            status = await self.middleware.call('vm.status', id)
            if status.get('state') == 'RUNNING':
                await self.middleware.call('vm.poweroff', id)
                # We would like to wait at least 7 seconds to have the vm
                # complete it's post vm actions which might require interaction with it's domain
                await asyncio.sleep(7)
            elif status.get('state') == 'ERROR' and not data.get('force'):
                raise CallError('Unable to retrieve VM status. Failed to destroy VM')

            if data['zvols']:
                devices = await self.middleware.call('vm.device.query', [
                    ('vm', '=', id), ('dtype', '=', 'DISK')
                ])

                for zvol in devices:
                    if not zvol['attributes']['path'].startswith('/dev/zvol/'):
                        continue

                    disk_name = zvol['attributes']['path'].rsplit(
                        '/dev/zvol/'
                    )[-1]
                    await self.middleware.call('zfs.dataset.delete', disk_name)

            await self.middleware.call('vm.undefine_vm', vm)

            # We remove vm devices first
            for device in vm['devices']:
                await self.middleware.call('vm.device.delete', device['id'])
            result = await self.middleware.call('datastore.delete', 'vm.vm', id)
            if not await self.middleware.call('vm.query'):
                await self.middleware.call('vm.deinitialize_vms')
                self.vms = {}
            return result

    @private
    def undefine_vm(self, vm):
        if vm['name'] in self.vms:
            self.vms.pop(vm['name']).undefine_domain()
        else:
            VMSupervisor(vm, self.libvirt_connection, self.middleware).undefine_domain()

    @private
    def ensure_libvirt_connection(self):
        if not self.libvirt_connection or not self.libvirt_connection.isAlive():
            raise CallError('Failed to connect to libvirt')

    @item_method
    @accepts(Int('id'), Dict('options', Bool('overcommit', default=False)))
    def start(self, id, options):
        """
        Start a VM.

        options.overcommit defaults to false, meaning VMs are not allowed to
        start if there is not enough available memory to hold all configured VMs.
        If true, VM starts even if there is not enough memory for all configured VMs.

        Error codes:

            ENOMEM(12): not enough free memory to run the VM without overcommit
        """
        vm = self.middleware.call_sync('vm.get_instance', id)
        self.ensure_libvirt_connection()
        if vm['status']['state'] == 'RUNNING':
            raise CallError(f'{vm["name"]} is already running')

        if self.validate_slots(vm):
            raise CallError(
                'Please adjust the devices attached to this VM. '
                f'A maximum of {LIBVIRT_AVAILABLE_SLOTS} PCI slots are allowed.'
            )

        flags = self.flags()

        if not flags['intel_vmx'] and not flags['amd_rvi']:
            raise CallError(
                'This system does not support virtualization.'
            )

        # Perhaps we should have a default config option for VMs?
        self.middleware.call_sync('vm.init_guest_vmemory', vm, options['overcommit'])

        # Passing vm_data will ensure that the domain/vm is started with latest changes registered
        # to the vm object
        self.vms[vm['name']].start(vm_data=vm)

    @item_method
    @accepts(
        Int('id'),
        Dict(
            'options',
            Bool('force', default=False),
            Bool('force_after_timeout', default=False),
        ),
    )
    @job(lock=lambda args: f'stop_vm_{args[0]}_{args[1].get("force") if len(args) == 2 else False}')
    def stop(self, job, id, options):
        """
        Stops a VM.

        For unresponsive guests who have exceeded the `shutdown_timeout` defined by the user and have become
        unresponsive, they required to be powered down using `vm.poweroff`. `vm.stop` is only going to send a
        shutdown signal to the guest and wait the desired `shutdown_timeout` value before tearing down guest vmemory.

        `force_after_timeout` when supplied, it will initiate poweroff for the VM forcing it to exit if it has
        not already stopped within the specified `shutdown_timeout`.
        """
        vm_data = self.middleware.call_sync('vm.get_instance', id)
        self.ensure_libvirt_connection()
        vm = self.vms[vm_data['name']]

        if options['force']:
            vm.poweroff()
        else:
            vm.stop(vm_data['shutdown_timeout'])

        if options['force_after_timeout'] and self.status(id)['state'] == 'RUNNING':
            vm.poweroff()

        self.middleware.call_sync('vm.teardown_guest_vmemory', id)

    @item_method
    @accepts(Int('id'))
    def poweroff(self, id):
        vm_data = self.middleware.call_sync('vm.get_instance', id)
        self.ensure_libvirt_connection()
        self.vms[vm_data['name']].poweroff()
        self.middleware.call_sync('vm.teardown_guest_vmemory', id)

    @item_method
    @accepts(Int('id'))
    @job(lock=lambda args: f'restart_vm_{args[0]}')
    def restart(self, job, id):
        """Restart a VM."""
        vm = self.middleware.call_sync('vm.get_instance', id)
        self.ensure_libvirt_connection()
        self.vms[vm['name']].restart(vm_data=vm, shutdown_timeout=vm['shutdown_timeout'])

    @private
    async def teardown_guest_vmemory(self, id):
        guest_status = await self.middleware.call('vm.status', id)
        if guest_status.get('state') != 'STOPPED':
            return

        vm = await self.middleware.call('datastore.query', 'vm.vm', [('id', '=', id)])
        guest_memory = vm[0].get('memory', 0) * 1024 * 1024
        arc_max = sysctl.filter('vfs.zfs.arc.max')[0].value
        arc_min = sysctl.filter('vfs.zfs.arc.min')[0].value
        new_arc_max = min(
            await self.middleware.call('vm.get_initial_arc_max'),
            arc_max + guest_memory
        )
        if arc_max != new_arc_max:
            if new_arc_max > arc_min:
                self.logger.debug(f'===> Give back guest memory to ARC: {new_arc_max}')
                sysctl.filter('vfs.zfs.arc.max')[0].value = new_arc_max
            else:
                self.logger.warn(
                    f'===> Not giving back memory to ARC because new arc_max ({new_arc_max}) <= arc_min ({arc_min})'
                )

    @item_method
    @accepts(Int('id'))
    def status(self, id):
        """Get the status of a VM.

        Returns a dict:
            - state, RUNNING or STOPPED
            - pid, process id if RUNNING
        """
        vm = self.middleware.call_sync('datastore.query', 'vm.vm', [['id', '=', id]], {'get': True})
        if self.libvirt_connection and vm['name'] in self.vms:
            try:
                # Whatever happens, query shouldn't fail
                return self.vms[vm['name']].status()
            except Exception:
                self.middleware.logger.debug(f'Failed to retrieve VM status for {vm["name"]}', exc_info=True)

        return {
            'state': 'ERROR',
            'pid': None,
            'domain_state': 'ERROR',
        }

    async def __next_clone_name(self, name):
        vm_names = [
            i['name']
            for i in await self.middleware.call('vm.query', [
                ('name', '~', rf'{name}{ZVOL_CLONE_SUFFIX}\d+')
            ])
        ]
        clone_index = 0
        while True:
            clone_name = f'{name}{ZVOL_CLONE_SUFFIX}{clone_index}'
            if clone_name not in vm_names:
                break
            clone_index += 1
        return clone_name

    async def __clone_zvol(self, name, zvol, created_snaps, created_clones):
        if not await self.middleware.call('zfs.dataset.query', [('id', '=', zvol)]):
            raise CallError(f'zvol {zvol} does not exist.', errno.ENOENT)

        snapshot_name = name
        i = 0
        while True:
            zvol_snapshot = f'{zvol}@{snapshot_name}'
            if await self.middleware.call('zfs.snapshot.query', [('id', '=', zvol_snapshot)]):
                if ZVOL_CLONE_RE.search(snapshot_name):
                    snapshot_name = ZVOL_CLONE_RE.sub(
                        rf'\1{ZVOL_CLONE_SUFFIX}{i}', snapshot_name,
                    )
                else:
                    snapshot_name = f'{name}{ZVOL_CLONE_SUFFIX}{i}'
                i += 1
                continue
            break

        await self.middleware.call('zfs.snapshot.create', {
            'dataset': zvol, 'name': snapshot_name,
        })
        created_snaps.append(zvol_snapshot)

        clone_suffix = name
        i = 0
        while True:
            clone_dst = f'{zvol}_{clone_suffix}'
            if await self.middleware.call('zfs.dataset.query', [('id', '=', clone_dst)]):
                if ZVOL_CLONE_RE.search(clone_suffix):
                    clone_suffix = ZVOL_CLONE_RE.sub(
                        rf'\1{ZVOL_CLONE_SUFFIX}{i}', clone_suffix,
                    )
                else:
                    clone_suffix = f'{name}{ZVOL_CLONE_SUFFIX}{i}'
                i += 1
                continue
            break

        if not await self.middleware.call('zfs.snapshot.clone', {
            'snapshot': zvol_snapshot, 'dataset_dst': clone_dst,
        }):
            raise CallError(f'Failed to clone {zvol_snapshot}.')

        created_clones.append(clone_dst)

        return clone_dst

    @item_method
    @accepts(Int('id'), Str('name', default=None))
    async def clone(self, id, name):
        """
        Clone the VM `id`.

        `name` is an optional parameter for the cloned VM.
        If not provided it will append the next number available to the VM name.
        """
        vm = await self.get_instance(id)

        origin_name = vm['name']
        del vm['id']
        del vm['status']

        vm['name'] = await self.__next_clone_name(vm['name'])

        if name is not None:
            vm['name'] = name

        # In case we need to rollback
        created_snaps = []
        created_clones = []
        try:
            for item in vm['devices']:
                item.pop('id', None)
                item.pop('vm', None)
                if item['dtype'] == 'NIC':
                    if 'mac' in item['attributes']:
                        del item['attributes']['mac']
                if item['dtype'] == 'VNC':
                    if 'vnc_port' in item['attributes']:
                        vnc_dict = await self.vnc_port_wizard()
                        item['attributes']['vnc_port'] = vnc_dict['vnc_port']
                if item['dtype'] == 'DISK':
                    zvol = item['attributes']['path'].replace('/dev/zvol/', '')
                    clone_dst = await self.__clone_zvol(
                        vm['name'], zvol, created_snaps, created_clones,
                    )
                    item['attributes']['path'] = f'/dev/zvol/{clone_dst}'
                if item['dtype'] == 'RAW':
                    item['attributes']['path'] = ''
                    self.logger.warn('For RAW disk you need copy it manually inside your NAS.')

            await self.do_create(vm)
        except Exception as e:
            for i in reversed(created_clones):
                try:
                    await self.middleware.call('zfs.dataset.delete', i)
                except Exception:
                    self.logger.warn('Rollback of VM clone left dangling zvol: %s', i)
            for i in reversed(created_snaps):
                try:
                    dataset, snap = i.split('@')
                    await self.middleware.call('zfs.snapshot.remove', {
                        'dataset': dataset,
                        'name': snap,
                        'defer_delete': True,
                    })
                except Exception:
                    self.logger.warn('Rollback of VM clone left dangling snapshot: %s', i)
            raise e
        self.logger.info('VM cloned from {0} to {1}'.format(origin_name, vm['name']))

        return True

    @accepts(Int('id'), Str('host', default=''))
    @pass_app()
    async def get_vnc_web(self, app, id, host=None):
        """
            Get the VNC URL from a given VM.

            Returns:
                list: With all URL available.
        """
        vnc_web = []

        host = host or await self.middleware.call('interface.websocket_local_ip', app=app)
        try:
            ipaddress.IPv6Address(host)
        except ipaddress.AddressValueError:
            pass
        else:
            host = f'[{host}]'

        for vnc_device in await self.get_vnc(id):
            if vnc_device.get('vnc_web'):
                vnc_web.append(
                    f'http://{host}:{VNC.get_vnc_web_port(vnc_device["vnc_port"])}/vnc.html?autoconnect=1'
                )

        return vnc_web

    @private
    def initialize_vms(self, timeout=10):
        if self.middleware.call_sync('vm.query'):
            self.middleware.call_sync('vm.wait_for_libvirtd', timeout)
        else:
            return

        # We use datastore.query specifically here to avoid a recursive case where vm.datastore_extend calls
        # status method which in turn needs a vm object to retrieve the libvirt status for the specified VM
        if self.libvirt_connection:
            for vm_data in self.middleware.call_sync('datastore.query', 'vm.vm'):
                vm_data['devices'] = self.middleware.call_sync('vm.device.query', [['vm', '=', vm_data['id']]])
                try:
                    self.vms[vm_data['name']] = VMSupervisor(vm_data, self.libvirt_connection, self.middleware)
                except Exception as e:
                    # Whatever happens, we don't want middlewared not booting
                    self.middleware.logger.error('Unable to setup %r VM object: %s', vm_data['name'], str(e))
        else:
            self.middleware.logger.error('Failed to establish libvirt connection')

    @private
    async def start_on_boot(self):
        for vm in await self.middleware.call('vm.query', [('autostart', '=', True)]):
            try:
                await self.middleware.call('vm.start', vm['id'])
            except Exception as e:
                self.middleware.logger.debug(f'Failed to start VM {vm["name"]}: {e}')


