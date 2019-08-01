from middlewared.async_validators import check_path_resides_within_volume
from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.schema import accepts, Error, Int, Str, Dict, List, Bool, Patch
from middlewared.service import (
    item_method, pass_app, private, CRUDService, CallError, ValidationErrors
)
from middlewared.utils import Nid, Popen, run
from middlewared.utils.path import is_child

import middlewared.logger
import asyncio
import errno
import ipaddress
import libvirt
import logging
import math
import netif
import os
import psutil
import random
import re
import stat
import subprocess
import sysctl
import shutil
import signal
import tempfile

from abc import ABC, abstractmethod
from collections import deque
from lxml import etree


logger = middlewared.logger.Logger('vm').getLogger()

BUFSIZE = 65536
LIBVIRT_URI = 'bhyve+unix:///system'
ZFS_ARC_MAX_INITIAL = None

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


class VMManager(object):

    def __init__(self, service):
        self.service = service
        self.logger = self.service.logger
        self._vm = {}

    async def start(self, vm):
        vid = vm['id']
        self._vm[vid] = VMSupervisor(self, vm)
        coro = self._vm[vid].run()
        # If run() has not returned in about 4 seconds we assume
        # bhyve process started successfully.
        done = (await asyncio.wait([coro], timeout=4))[0]
        if done:
            list(done)[0].result()

    async def stop(self, id, force=False):
        supervisor = self._vm.get(id)
        if not supervisor:
            return False

        err = await supervisor.stop(force)
        return err

    async def restart(self, id):
        supervisor = self._vm.get(id)
        if supervisor:
            await supervisor.restart()
            return True
        else:
            return False

    async def status(self, id):
        supervisor = self._vm.get(id)
        if supervisor and await supervisor.running():
            return {
                'state': 'RUNNING',
                'pid': supervisor.proc.pid if supervisor.proc else None,
            }
        else:
            return {
                'state': 'STOPPED',
                'pid': None,
            }


class VMSupervisorLibVirt:

    def __init__(self, vm_data, connection, logger_obj=None, log_format=None, debug_level=None):
        self.vm_data = vm_data
        self.connection = connection
        if not self.connection or not self.connection.isAlive():
            raise CallError(f'Failed to connect to libvirtd for {self.vm_data["name"]}')

        # Setup logging
        if logger_obj:
            self.logger = logger_obj.getChild(f'vm_{vm_data["name"]}')

            handler = logger_obj.ErrorProneRotatingFileHandler(
                f'/var/log/vm/{self.vm_data["name"]}_{self.vm_data["id"]}',
                maxBytes=10485760,
                backupCount=5,
            )
            handler.setFormatter(logging.Formatter(log_format))
            self.logger.addHandler(handler)  # main log + vm specific log
            self.logger.setLevel(debug_level)
        else:
            # FIXME: Done for dev purposes for a while
            self.logger = None

    @property
    def domain(self):
        try:
            return self.connection.lookupByName(self.vm_data['name'])
        except libvirt.libvirtError:
            return None

    def construct_xml(self):
        domain = create_element(
            'domain', type='bhyve', id=str(self.vm_data['id']), attribute_dict={
                'children': [
                    create_element('name', attribute_dict={'text': f'{self.vm_data["id"]}_{self.vm_data["name"]}'}),
                    create_element('title', attribute_dict={'text': self.vm_data['name']}),
                    create_element('description', attribute_dict={'text': self.vm_data['description']}),
                    # OS/boot related xml
                    self.os_xml(),
                    # VCPU related xml
                    create_element('vcpu', attribute_dict={'text': str(self.vm_data['vcpus'])}),
                    # Memory related xml
                    create_element('memory', unit='M', attribute_dict={'text': str(self.vm_data['memory'])}),
                    # Add features
                    create_element(
                        'features', attribute_dict={
                            'children': [
                                create_element('acpi'),
                                create_element('apic'),
                            ]
                        }
                    ),
                    # Clock offset
                    create_element('clock', offset='localtime' if self.vm_data['time'] == 'LOCAL' else 'utc'),
                ]
            }
        )

        return domain

    def os_xml(self):
        children = [create_element('type', attribute_dict={'text': 'hvm'})]
        if self.vm_data['bootloader'] in ('UEFI', 'UEFI_CSM'):
            children.append(
                create_element(
                    'loader', attribute_dict={
                        'text': '/usr/local/share/uefi-firmware/BHYVE_UEFI'
                        f'{"_CSM" if self.vm_data["bootloader"] == "UEFI_CSM" else ""}.fd'
                    }, readonly='yes', type='pflash',
                ),  # FIXME: Add host-bootloader support i.e grub-bhyve
                # FIXME: Please test for BIOS
            )
        os_element = create_element('os', attribute_dict={'children': children})

        return os_element


class Device(ABC):

    schema = NotImplemented

    def __init__(self, data):
        self.data = data

    @abstractmethod
    def xml(self, *args, **kwargs):
        pass


class Disk(Device):

    schema = Dict(
        'attributes',
        Str('path'),
        Str('type', enum=['AHCI', 'VIRTIO'], default='AHCI'),
        Bool('create_zvol'),
        Str('zvol_name'),
        Int('zvol_volsize'),
        Int('sectorsize', enum=[0, 512, 4096], default=0),
    )

    def __init__(self, data):
        super().__init__(data)

    def xml(self, *args, **kwargs):
        child_element = kwargs.pop('child_element')
        return create_element(
            'disk', type='file', device='disk', attribute_dict={
                'children': [
                    create_element('source', file=self.data['attributes']['path']),
                    create_element('target', dev=f'hdc{self.data["id"]}', bus='sata'),
                    child_element,
                ]
            }
        )


class CDROM(Device):

    schema = Dict(
        'attributes',
        Str('path', required=True),
    )


class RAW(Device):

    schema = Dict(
        'attributes',
        Str('path', required=True),
        Str('type', enum=['AHCI', 'VIRTIO'], default='AHCI'),
        Bool('exists'),
        Bool('boot', default=False),
        Int('size', default=None, null=True),
        Int('sectorsize', enum=[0, 512, 4096], default=0),
    )


class NIC(Device):

    schema = Dict(
        'attributes',
        Str('type', enum=['E1000', 'VIRTIO'], default='E1000'),
        Str('nic_attach', default=None, null=True),
        Str('mac'),
    )


class VNC(Device):

    schema = Dict(
        'attributes',
        Str('vnc_resolution', enum=[
            '1920x1200', '1920x1080', '1600x1200', '1600x900',
            '1400x1050', '1280x1024', '1280x720',
            '1024x768', '800x600', '640x480',
        ], default='1024x768'),
        Int('vnc_port', default=None, null=True),
        Str('vnc_bind'),
        Bool('wait', default=False),
        Str('vnc_password', default=None, null=True, private=True),
        Bool('vnc_web', default=False),
    )


class VMSupervisor(object):

    def __init__(self, manager, vm):
        self.manager = manager

        os.makedirs('/var/log/vm', exist_ok=True)
        self.logger = self.manager.logger.getChild(f'vm_{vm["id"]}')

        handler = middlewared.logger.ErrorProneRotatingFileHandler(
            f'/var/log/vm/{vm["name"]}_{vm["id"]}',
            maxBytes=10485760,
            backupCount=5,
        )
        self.middleware = self.manager.service.middleware

        handler.setFormatter(logging.Formatter(self.middleware.log_format))
        self.logger.addHandler(handler)  # main log + vm specific log
        self.logger.setLevel(self.middleware.debug_level)

        self.vm = vm
        self.proc = None
        self.grub_proc = None
        self.web_proc = None
        self.taps = []
        self.bhyve_error = None

    async def run(self):
        vnc_web = None  # We need to initialize before line 200
        args = [
            'bhyve',
            '-A',
            '-H',
            '-w',
            '-c', str(self.vm['vcpus']),
            '-m', str(self.vm['memory']),
            '-s', '0:0,hostbridge',
            '-s', '31,lpc',
            '-l', 'com1,/dev/nmdm{}A'.format(self.vm['id']),
        ]

        if self.vm['bootloader'] in ('UEFI', 'UEFI_CSM'):
            args += [
                '-l', 'bootrom,/usr/local/share/uefi-firmware/BHYVE_UEFI{}.fd'.format('_CSM' if self.vm['bootloader'] == 'UEFI_CSM' else ''),
            ]

        if self.vm['time'] == 'UTC':
            args += ['-u']

        nid = Nid(3)
        grub_devices = []
        block_devices = {
            'ahci': [],
            'virtio-blk': [],
        }
        for device in sorted(self.vm['devices'], key=lambda x: (x['order'], x['id'])):
            if device['dtype'] in ('CDROM', 'DISK', 'RAW'):

                # Get grub devices to be used in grub-bhyve
                if device['dtype'] == 'RAW' and device['attributes'].get('boot'):
                    grub_devices.append(device['attributes']['path'])

                disk_sector_size = int(device['attributes'].get('sectorsize') or 0)
                if disk_sector_size > 0:
                    sectorsize_args = ',sectorsize=' + str(disk_sector_size)
                else:
                    sectorsize_args = ''

                if device['dtype'] == 'CDROM':
                    block_name = 'ahci'
                    suffix = 'cd:'
                elif device['attributes'].get('type') == 'AHCI':
                    block_name = 'ahci'
                    suffix = 'hd:'
                else:
                    block_name = 'virtio-blk'
                    suffix = ''

                # Each block PCI slot takes up to 8 functions
                # ahci can take up to 32 disks per function
                # virtio-blk occupies the entire function
                for block in block_devices[block_name]:
                    if len(block['disks']) < (256 if block_name == 'ahci' else 8):
                        break
                else:
                    block = {
                        'slot': nid(),
                        'disks': []
                    }
                    block_devices[block_name].append(block)
                block['disks'].append(f'{suffix}{device["attributes"]["path"]}{sectorsize_args}')

            elif device['dtype'] == 'NIC':
                attach_iface = device['attributes'].get('nic_attach')

                self.logger.debug('====> NIC_ATTACH: {0}'.format(attach_iface))

                tapname = netif.create_interface('tap')
                tap = netif.get_interface(tapname)
                tap.description = f'Attached to {self.vm["name"]}'
                tap.up()
                self.taps.append(tapname)
                await self.bridge_setup(tapname, tap, attach_iface)

                if device['attributes'].get('type') == 'VIRTIO':
                    nictype = 'virtio-net'
                else:
                    nictype = 'e1000'
                mac_address = device['attributes'].get('mac', None)

                # By default we add one NIC and the MAC address is an empty string.
                # Issue: 24222
                if mac_address == '':
                    mac_address = None

                if mac_address == '00:a0:98:FF:FF:FF' or mac_address is None:
                    random_mac = await self.middleware.call('vm.random_mac')
                    args += ['-s', '{},{},{},mac={}'.format(nid(), nictype, tapname, random_mac)]
                else:
                    args += ['-s', '{},{},{},mac={}'.format(nid(), nictype, tapname, mac_address)]
            elif device['dtype'] == 'VNC':
                if device['attributes'].get('wait'):
                    wait = 'wait'
                else:
                    wait = ''

                vnc_resolution = device['attributes'].get('vnc_resolution', None)
                vnc_port = int(device['attributes'].get('vnc_port') or (5900 + self.vm['id']))
                vnc_bind = device['attributes'].get('vnc_bind', '0.0.0.0')
                vnc_password = device['attributes'].get('vnc_password', None)
                vnc_web = device['attributes'].get('vnc_web', None)

                vnc_password_args = ''
                if vnc_password:
                    vnc_password_args = 'password=' + vnc_password

                if vnc_resolution is None:
                    width = 1024
                    height = 768
                else:
                    vnc_resolution = vnc_resolution.split('x')
                    width = vnc_resolution[0]
                    height = vnc_resolution[1]

                args += ['-s', '29,fbuf,vncserver,tcp={}:{},w={},h={},{},{}'.format(vnc_bind, vnc_port, width,
                                                                                    height, vnc_password_args, wait),
                         '-s', '30,xhci,tablet', ]

        for pciemu, pcislots in block_devices.items():
            perfunction = 32 if pciemu == 'ahci' else 1
            for pcislot in pcislots:
                for pcifunc in range(math.ceil(len(pcislot['disks']) / perfunction)):
                    conf = ','.join(pcislot['disks'][
                        pcifunc * perfunction:(pcifunc + 1) * perfunction
                    ])
                    args += ['-s', f'{pcislot["slot"]}:{pcifunc},{pciemu},{conf}']

        # grub-bhyve support
        device_map_file = tempfile.NamedTemporaryFile()
        grub_dir = None
        if self.vm['bootloader'] == 'GRUB':

            if not grub_devices:
                raise CallError(f'There is no boot disk for vm: {self.vm["name"]}')

            for i, device in enumerate(grub_devices):
                device_map_file.write(f'(hd{i}) {device}\n'.encode())
            device_map_file.flush()

            if (
                self.vm['grubconfig'] and
                self.vm['grubconfig'].startswith('/mnt/') and
                os.path.exists(self.vm['grubconfig'])
            ):
                grub_dir = os.path.dirname(self.vm['grubconfig'])
            else:
                grub_dir = f'/tmp/grub/{self.vm["id"]}_{self.vm["name"]}'
                os.makedirs(grub_dir, exist_ok=True)
                grub_file = os.path.join(grub_dir, 'grub.cfg')
                with open(grub_file, 'w') as f:
                    f.write(self.vm['grubconfig'])

            grub_bhyve_args = [
                'grub-bhyve', '-m', device_map_file.name,
                '-r', 'host',
                '-M', str(self.vm['memory']),
                '-d', grub_dir,
                str(self.vm['id']) + '_' + self.vm['name'],
            ]

            self.logger.debug(f'Starting grub-bhyve: {" ".join(grub_bhyve_args)}')
            self.grub_proc = await Popen(
                grub_bhyve_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )

            try:
                await asyncio.wait_for(self.grub_proc.communicate(), 2)
            except asyncio.TimeoutError:
                try:
                    os.kill(self.grub_proc.pid, signal.SIGKILL)
                except OSError:
                    pass
                await self.destroy_vm()
                raise CallError('grub-bhyve timed out, please check your grub config.')

        args.append(str(self.vm['id']) + '_' + self.vm['name'])

        self.logger.debug('Starting bhyve: {}'.format(' '.join(args)))
        self.proc = await Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        if vnc_web:
            split_port = int(str(vnc_port)[:2]) - 1
            vnc_web_port = str(split_port) + str(vnc_port)[2:]

            web_bind = ':{}'.format(vnc_web_port) if vnc_bind == '0.0.0.0' else '{}:{}'.format(vnc_bind, vnc_web_port)

            self.web_proc = await Popen(['/usr/local/libexec/novnc/utils/websockify/run', '--web',
                                         '/usr/local/libexec/novnc/', '--wrap-mode=ignore',
                                         web_bind, '{}:{}'.format(vnc_bind, vnc_port)],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.logger.debug('==> Start WEBVNC at port {} with pid number {}'.format(vnc_web_port, self.web_proc.pid))

        output = deque(maxlen=10)

        while True:
            line = await self.proc.stdout.readline()
            if line == b'':
                break
            line = line.decode().rstrip()
            self.logger.debug('{}: {}'.format(self.vm['name'], line))
            output.append(line)

        # Clean up grub files
        if device_map_file:
            device_map_file.close()
        if grub_dir and not (self.vm['grubconfig'] or '').startswith(grub_dir):
            shutil.rmtree(grub_dir)

        # bhyve returns the following status code:
        # 0 - VM has been reset
        # 1 - VM has been powered off
        # 2 - VM has been halted
        # 3 - VM generated a triple fault
        # 4 - VM exited due to an error
        # all other non-zero status codes are errors
        self.bhyve_error = await self.proc.wait()
        if self.bhyve_error == 0:
            self.logger.info('===> Rebooting VM: {0} ID: {1} BHYVE_CODE: {2}'.format(self.vm['name'], self.vm['id'], self.bhyve_error))
            await self.manager.restart(self.vm['id'])
            await self.manager.start(self.vm)
        elif self.bhyve_error == 1:
            # XXX: Need a better way to handle the vmm destroy.
            self.logger.info('===> Powered off VM: {0} ID: {1} BHYVE_CODE: {2}'.format(self.vm['name'], self.vm['id'], self.bhyve_error))
            await self.__teardown_guest_vmemory(self.vm['id'])
            await self.destroy_vm()
        elif self.bhyve_error in (2, 3):
            self.logger.info('===> Stopping VM: {0} ID: {1} BHYVE_CODE: {2}'.format(self.vm['name'], self.vm['id'], self.bhyve_error))
            await self.__teardown_guest_vmemory(self.vm['id'])
            await self.manager.stop(self.vm['id'])
        elif self.bhyve_error not in (0, 1, 2, 3, None):
            self.logger.info('===> Error VM: {0} ID: {1} BHYVE_CODE: {2}'.format(self.vm['name'], self.vm['id'], self.bhyve_error))
            await self.__teardown_guest_vmemory(self.vm['id'])
            await self.destroy_vm()
            output = "\n".join(output)
            raise CallError(f'VM {self.vm["name"]} failed to start: {output}')

    async def destroy_vm(self):
        self.logger.warn('===> Destroying VM: {0} ID: {1} BHYVE_CODE: {2}'.format(self.vm['name'], self.vm['id'], self.bhyve_error))
        # XXX: We need to catch the bhyvectl return error.
        await (await Popen(['bhyvectl', '--destroy', '--vm={}'.format(str(self.vm['id']) + '_' + self.vm['name'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE)).wait()
        self.manager._vm.pop(self.vm['id'], None)
        await self.kill_bhyve_web()
        self.destroy_tap()

    async def __teardown_guest_vmemory(self, id):
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

    def destroy_tap(self):
        while self.taps:
            netif.destroy_interface(self.taps.pop())

    def set_iface_mtu(self, ifacesrc, ifacedst):
        ifacedst.mtu = ifacesrc.mtu

        return ifacedst

    async def bridge_setup(self, tapname, tap, attach_iface):
        if_bridge = []
        bridge_enabled = False

        if tapname == attach_iface:
            raise CallError(f'VM cannot bridge with its own interface ({tapname}).')

        if attach_iface is None:
            # XXX: backward compatibility prior to 11.1-RELEASE.
            try:
                attach_iface = netif.RoutingTable().default_route_ipv4.interface
                attach_iface_info = netif.get_interface(attach_iface)
            except Exception:
                return
        else:
            attach_iface_info = netif.get_interface(attach_iface)

        # If for some reason the main iface is down, we need to up it.
        attach_iface_status = netif.InterfaceFlags.UP in attach_iface_info.flags
        if attach_iface_status is False:
            attach_iface_info.up()

        for brgname, iface in list(netif.list_interfaces().items()):
            if brgname.startswith('bridge'):
                if_bridge.append(iface)

        for bridge in if_bridge:
            if attach_iface in bridge.members:
                bridge_enabled = True
                self.set_iface_mtu(attach_iface_info, tap)
                bridge.add_member(tapname)
                if netif.InterfaceFlags.UP not in bridge.flags:
                    bridge.up()
                break

        if bridge_enabled is False:
            bridge = netif.get_interface(netif.create_interface('bridge'))
            self.set_iface_mtu(attach_iface_info, tap)
            bridge.add_member(tapname)
            bridge.add_member(attach_iface)
            bridge.up()

    async def kill_bhyve_pid(self):
        if self.proc:
            try:
                os.kill(self.proc.pid, signal.SIGTERM)
            except ProcessLookupError as e:
                # Already stopped, process do not exist anymore
                if e.errno != errno.ESRCH:
                    raise
            return True

    async def kill_bhyve_web(self):
        if self.web_proc:
            try:
                self.logger.debug('==> Killing WEBVNC: {}'.format(self.web_proc.pid))
                os.kill(self.web_proc.pid, signal.SIGTERM)
            except ProcessLookupError as e:
                if e.errno != errno.ESRCH:
                    raise
            return True

    async def restart(self):
        bhyve_error = await (await Popen(['bhyvectl', '--force-reset', '--vm={}'.format(str(self.vm['id']) + '_' + self.vm['name'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE)).wait()
        self.logger.debug('==> Reset VM: {0} ID: {1} BHYVE_CODE: {2}'.format(self.vm['name'], self.vm['id'], bhyve_error))
        self.destroy_tap()
        await self.kill_bhyve_web()

    async def stop(self, force=False):
        if force:
            bhyve_error = await (await Popen(['bhyvectl', '--force-poweroff', '--vm={}'.format(str(self.vm['id']) + '_' + self.vm['name'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE)).wait()
            self.logger.debug('===> Force Stop VM: {0} ID: {1} BHYVE_CODE: {2}'.format(self.vm['name'], self.vm['id'], self.bhyve_error))
            if bhyve_error:
                self.logger.error('===> Stopping VM error: {0}'.format(bhyve_error))
        else:
            self.logger.debug('===> Soft Stop VM: {0} ID: {1}'.format(self.vm['name'], self.vm['id']))

        self.destroy_tap()
        return await self.kill_bhyve_pid()

    async def running(self):
        bhyve_error = await (await Popen(['bhyvectl', '--vm={}'.format(str(self.vm['id']) + '_' + self.vm['name'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE)).wait()
        if bhyve_error == 0:
            if self.proc:
                try:
                    os.kill(self.proc.pid, 0)
                except OSError:
                    self.logger.error('===> VMM {0} is running without bhyve process.'.format(self.vm['name']))
                    return False
                return True
            else:
                # XXX: We return true for now to keep the vm.status sane.
                # It is necessary handle in a better way the bhyve process associated with the vmm.
                return True
        elif bhyve_error == 1:
            return False


class VMService(CRUDService):

    class Config:
        namespace = 'vm'
        datastore = 'vm.vm'
        datastore_extend = 'vm._extend_vm'

    def __init__(self, *args, **kwargs):
        super(VMService, self).__init__(*args, **kwargs)
        self._manager = VMManager(self)
        os.makedirs('/var/log/vm', exist_ok=True)

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

        rvi = sysctl.filter('hw.vmm.svm.features')
        data['amd_rvi'] = True if rvi and rvi[0].value != 0 and not intel \
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

    async def _extend_vm(self, vm):
        vm['devices'] = await self.middleware.call('vm.device.query', [('vm', '=', vm['id'])])
        vm['status'] = await self.status(vm['id'])
        return vm

    @accepts(Int('id'))
    async def get_vnc(self, id):
        """
        Get the vnc devices from a given guest.

        Returns:
            list(dict): with all attributes of the vnc device or an empty list.
        """
        vnc_devices = []
        for device in await self.middleware.call('datastore.query', 'vm.device', [('vm__id', '=', id)]):
            if device['dtype'] == 'VNC':
                vnc = device['attributes']
                vnc_devices.append(vnc)
        return vnc_devices

    @accepts()
    def vnc_port_wizard(self):
        """
        It returns the next available VNC PORT and WEB VNC PORT.

        Returns:
            dict: with two keys vnc_port and vnc_web or None in case we can't query the db.
        """
        vnc_ports_in_use = []
        vms = self.middleware.call_sync('datastore.query', 'vm.vm', [], {'order_by': ['id']})

        if vms:
            latest_vm_id = vms.pop().get('id', None)
            vnc_port = 5900 + latest_vm_id + 1

            check_vnc_device = self.middleware.call_sync('datastore.query', 'vm.device', [('dtype', '=', 'VNC')])
            for vnc in check_vnc_device:
                vnc_used_port = vnc['attributes'].get('vnc_port', None)
                if vnc_used_port is None:
                    vm_id = vnc['vm'].get('id', None)
                    vnc_ports_in_use.append(5900 + vm_id)
                else:
                    vnc_ports_in_use.append(int(vnc_used_port))

            auto_generate = True
            while auto_generate:
                if vnc_port in vnc_ports_in_use:
                    vnc_port = vnc_port + 1
                else:
                    auto_generate = False
                    split_port = int(str(vnc_port)[:2]) - 1
                    vnc_web = int(str(split_port) + str(vnc_port)[2:])
                    vnc_attr = {'vnc_port': vnc_port, 'vnc_web': vnc_web}
        else:
            return None
        return vnc_attr

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
        for device in await self.middleware.call('datastore.query', 'vm.device', [('vm__id', '=', id)]):
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
            guest_status = await self.status(id)
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
            status = await self.status(guest['id'])
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

    @private
    async def get_initial_arc_max(self):
        tunable = await self.middleware.call('tunable.query', [
            ('type', '=', 'SYSCTL'), ('var', '=', 'vfs.zfs.arc.max')
        ])
        if tunable:
            try:
                return int(tunable[0]['value'])
            except ValueError:
                pass
        return ZFS_ARC_MAX_INITIAL

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

    async def __init_guest_vmemory(self, vm, overcommit):
        guest_memory = vm.get('memory', None)
        guest_status = await self.status(vm['id'])
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
        mac_address = [0x00, 0xa0, 0x98, random.randint(0x00, 0x7f), random.randint(0x00, 0xff), random.randint(0x00, 0xff)]
        return ':'.join(['%02x' % x for x in mac_address])

    @accepts(Dict(
        'vm_create',
        Str('name', required=True),
        Str('description'),
        Int('vcpus', default=1),
        Int('memory', required=True),
        Str('bootloader', enum=['UEFI', 'UEFI_CSM', 'GRUB']),
        Str('grubconfig', null=True),
        List('devices', default=[], items=[Patch('vmdevice_create', 'vmdevice_update', ('rm', {'name': 'vm'}))]),
        Bool('autostart', default=True),
        Str('time', enum=['LOCAL', 'UTC'], default='LOCAL'),
        register=True,
    ))
    async def do_create(self, data):
        """
        Create a Virtual Machine (VM).

        `grubconfig` may either be a path for the grub.cfg file or the actual content
        of the file to be used with GRUB bootloader.

        `devices` is a list of virtualized hardware to add to the newly created Virtual Machine.
        Failure to attach a device destroys the VM and any resources allocated by the VM devices.
        """

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

        return await self._get_instance(vm_id)

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

        vcpus = data.get('vcpus')
        if vcpus:
            flags = await self.middleware.call('vm.flags')
            if flags['intel_vmx']:
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
                await self.middleware.call('vm.device.validate_device', device, devices_ids.get(device.get('id')))
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

        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)

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

        return await self._get_instance(id)

    @accepts(
        Int('id'),
        Dict(
            'vm_delete',
            Bool('zvols', default=False),
        ),
    )
    async def do_delete(self, id, data):
        """Delete a VM."""
        status = await self.status(id)
        if isinstance(status, dict):
            if status.get('state') == 'RUNNING':
                await self.stop(id)
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
        return await self.middleware.call('datastore.delete', 'vm.vm', id)

    @item_method
    @accepts(Int('id'), Dict('options', Bool('overcommit')))
    async def start(self, id, options):
        """
        Start a VM.

        options.overcommit defaults to false, meaning VMs are not allowed to
        start if there is not enough available memory to hold all configured VMs.
        If true, VM starts even if there is not enough memory for all configured VMs.

        Error codes:

            ENOMEM(12): not enough free memory to run the VM without overcommit
        """
        vm = await self._get_instance(id)
        flags = await self.middleware.call('vm.flags')

        if not flags['intel_vmx'] and not flags['amd_rvi']:
            raise CallError(
                'This system does not support virtualization.'
            )

        overcommit = options.get('overcommit')

        if overcommit is None:
            # Perhaps we should have a default config option for VMs?
            overcommit = False

        await self.__init_guest_vmemory(vm, overcommit=overcommit)
        await self._manager.start(vm)

    @item_method
    @accepts(Int('id'), Bool('force', default=False),)
    async def stop(self, id, force):
        """Stop a VM."""
        try:
            return await self._manager.stop(id, force)
        except Exception as err:
            self.logger.error('===> {0}'.format(err))
            return False

    @item_method
    @accepts(Int('id'))
    async def restart(self, id):
        """Restart a VM."""
        try:
            return await self._manager.restart(id)
        except Exception as err:
            self.logger.error('===> {0}'.format(err))
            return False

    @item_method
    @accepts(Int('id'))
    async def status(self, id):
        """Get the status of a VM.

        Returns a dict:
            - state, RUNNING or STOPPED
            - pid, process id if RUNNING
        """
        return await self._manager.status(id)

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

        if not await self.middleware.call('zfs.snapshot.create', {
            'dataset': zvol, 'name': snapshot_name,
        }):
            raise CallError(f'Failed to snapshot {zvol_snapshot}.')

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
        vm = await self._get_instance(id)

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
                        vnc_dict = await self.middleware.call(
                            'vm.vnc_port_wizard')
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

            await self.create(vm)
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
    @pass_app
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
            if vnc_device.get('vnc_web', None) is True:
                vnc_port = vnc_device.get('vnc_port', None)
                if vnc_port is None:
                    vnc_port = 5900 + id
                #  XXX: Create a method for web port.
                split_port = int(str(vnc_port)[:2]) - 1
                vnc_web_port = str(split_port) + str(vnc_port)[2:]
                vnc_web.append(
                    f'http://{host}:{vnc_web_port}/vnc.html?autoconnect=1'
                )

        return vnc_web


class VMDeviceService(CRUDService):

    DEVICE_ATTRS = {
        'CDROM': CDROM.schema,
        'RAW': RAW.schema,
        'DISK': Disk.schema,
        'NIC': NIC.schema,
        'VNC': VNC.schema,
    }

    class Config:
        namespace = 'vm.device'
        datastore = 'vm.device'
        datastore_extend = 'vm.device.extend_device'

    @private
    async def create_resource(self, device, old=None):
        return (
            (device['dtype'] == 'DISK' and device['attributes'].get('create_zvol')) or (
                device['dtype'] == 'RAW' and (not device['attributes'].get('exists', True) or (
                    old and old['attributes'].get('size') != device['attributes'].get('size')
                ))
            )
        )

    @private
    async def extend_device(self, device):
        if device['vm']:
            device['vm'] = device['vm']['id']
        if device['order'] is None:
            if device['dtype'] == 'CDROM':
                device['order'] = 1000
            elif device['dtype'] in ('DISK', 'RAW'):
                device['order'] = 1001
            else:
                device['order'] = 1002
        return device

    @accepts()
    def nic_attach_choices(self):
        """
        Available choices for NIC Attach attribute.
        """
        return self.middleware.call_sync('interface.choices', {
            'exclude': ['bridge', 'epair', 'tap', 'vnet'],
        })

    @accepts()
    def vnc_bind_choices(self):
        """
        Available choices for VNC Bind attribute.
        """
        return {
            i['address']: i['address']
            for i in self.middleware.call_sync('interface.ip_in_use', {
                'any': True,
                'loopback': True,
            })
        }

    @private
    async def update_device(self, data, old=None):
        if data['dtype'] == 'DISK':
            create_zvol = data['attributes'].pop('create_zvol', False)

            if create_zvol:
                ds_options = {
                    'name': data['attributes'].pop('zvol_name'),
                    'type': 'VOLUME',
                    'volsize': data['attributes'].pop('zvol_volsize'),
                }

                self.logger.debug(
                    f'Creating ZVOL {ds_options["name"]} with volsize {ds_options["volsize"]}'
                )

                zvol_blocksize = await self.middleware.call(
                    'pool.dataset.recommended_zvol_blocksize', ds_options['name'].split('/', 1)[0]
                )
                ds_options['volblocksize'] = zvol_blocksize

                new_zvol = (await self.middleware.call('pool.dataset.create', ds_options))['id']
                data['attributes']['path'] = f'/dev/zvol/{new_zvol}'
        elif data['dtype'] == 'RAW' and (
            not data['attributes'].pop('exists', True) or (
                old and old['attributes']['size'] != data['attributes']['size']
            )
        ):
            path = data['attributes']['path']
            cp = await run(['truncate', '-s', str(data['attributes']['size']), path], check=False)
            if cp.returncode:
                raise CallError(f'Failed to create or update raw file {path}: {cp.stderr}')

        return data

    @accepts(
        Dict(
            'vmdevice_create',
            Str('dtype', enum=['NIC', 'DISK', 'CDROM', 'VNC', 'RAW'], required=True),
            Int('vm', required=True),
            Dict('attributes', additional_attrs=True, default=None),
            Int('order', default=None, null=True),
            register=True,
        ),
    )
    async def do_create(self, data):
        """
        Create a new device for the VM of id `vm`.

        If `dtype` is the `RAW` type and a new raw file is to be created, `attributes.exists` will be passed as false.
        This means the API handles creating the raw file and raises the appropriate exception if file creation fails.

        If `dtype` is of `DISK` type and a new Zvol is to be created, `attributes.create_zvol` will be passed as
        true with valid `attributes.zvol_name` and `attributes.zvol_volsize` values.
        """
        data = await self.validate_device(data)
        data = await self.update_device(data)

        id = await self.middleware.call(
            'datastore.insert', self._config.datastore, data
        )
        await self.__reorder_devices(id, data['vm'], data['order'])

        return await self._get_instance(id)

    @accepts(Int('id'), Patch(
        'vmdevice_create',
        'vmdevice_update',
        ('attr', {'update': True}),
    ))
    async def do_update(self, id, data):
        """
        Update a VM device of `id`.

        Pass `attributes.size` to resize a `dtype` `RAW` device. The raw file will be resized.
        """
        device = await self._get_instance(id)
        new = device.copy()
        new.update(data)

        new = await self.validate_device(new, device)
        new = await self.update_device(new, device)

        await self.middleware.call('datastore.update', self._config.datastore, id, new)
        await self.__reorder_devices(id, device['vm'], new['order'])

        return await self._get_instance(id)

    @private
    async def delete_resource(self, options, device):
        if options['zvol']:
            if device['dtype'] != 'DISK':
                raise CallError('The device is not a disk and has no zvol to destroy.')
            zvol_id = device['attributes'].get('path', '').rsplit('/dev/zvol/')[-1]
            if await self.middleware.call('pool.dataset.query', [['id', '=', zvol_id]]):
                # FIXME: We should use pool.dataset.delete but right now FS attachments will consider
                # the current device as a valid reference. Also should we stopping the vm only when deleting an
                # attachment ?
                await self.middleware.call('zfs.dataset.delete', zvol_id)
        if options['raw_file']:
            if device['dtype'] != 'RAW':
                raise CallError('Device is not of RAW type.')
            try:
                os.unlink(device['attributes']['path'])
            except OSError:
                raise CallError(f'Failed to destroy {device["attributes"]["path"]}')

    @accepts(
        Int('id'),
        Dict(
            'vm_device_delete',
            Bool('zvol', default=False),
            Bool('raw_file', default=False),
        )
    )
    async def do_delete(self, id, options):
        """
        Delete a VM device of `id`.
        """
        await self.delete_resource(options, (await self._get_instance(id)))

        return await self.middleware.call('datastore.delete', self._config.datastore, id)

    async def __reorder_devices(self, id, vm_id, order):
        if order is None:
            return
        filters = [('vm', '=', vm_id), ('id', '!=', id)]
        if await self.middleware.call('vm.device.query', filters + [
            ('order', '=', order)
        ]):
            used_order = [order]
            for device in await self.middleware.call(
                'vm.device.query', filters, {'order_by': ['order']}
            ):
                if device['order'] is None:
                    continue

                if device['order'] not in used_order:
                    used_order.append(device['order'])
                    continue

                device['order'] = min(used_order) + 1
                while device['order'] in used_order:
                    device['order'] += 1
                used_order.append(device['order'])
                await self.middleware.call(
                    'datastore.update', self._config.datastore, device['id'], device
                )

    @private
    async def validate_device(self, device, old=None):
        vm_instance = await self.middleware.call('vm._get_instance', device['vm']) if device.get('vm') else None

        verrors = ValidationErrors()
        schema = self.DEVICE_ATTRS.get(device['dtype'])
        if schema:
            try:
                device['attributes'] = schema.clean(device['attributes'])
            except Error as e:
                verrors.add(f'attributes.{e.attribute}', e.errmsg, e.errno)

            try:
                schema.validate(device['attributes'])
            except ValidationErrors as e:
                verrors.extend(e)

            if verrors:
                raise verrors

        if device.get('dtype') == 'DISK':
            if 'attributes' not in device:
                verrors.add('attributes', 'This field is required.')
                raise verrors
            create_zvol = device['attributes'].get('create_zvol')
            path = device['attributes'].get('path')
            if create_zvol:
                for attr in ('zvol_name', 'zvol_volsize'):
                    if not device['attributes'].get(attr):
                        verrors.add(
                            f'attributes.{attr}',
                            'This field is required.'
                        )
                parentzvol = (device['attributes'].get('zvol_name') or '').rsplit('/', 1)[0]
                if parentzvol and not await self.middleware.call(
                    'pool.dataset.query', [('id', '=', parentzvol)]
                ):
                    verrors.add(
                        'attributes.zvol_name',
                        f'Parent dataset {parentzvol} does not exist.',
                        errno.ENOENT
                    )
                if not verrors and create_zvol and await self.middleware.call(
                    'pool.dataset.query', [['id', '=', device['attributes']['zvol_name']]]
                ):
                    verrors.add(
                        'attributes.zvol_name',
                        f'{device["attributes"]["zvol_name"]} already exists.'
                    )
            elif not path:
                verrors.add('attributes.path', 'Disk path is required.')
            elif path and not os.path.exists(path):
                verrors.add('attributes.path', f'Disk path {path} does not exist.', errno.ENOENT)

            if path and len(path) > 63:
                # SPECNAMELEN is not long enough (63) in 12, 13 will be 255
                verrors.add(
                    'attributes.path',
                    f'Disk path {path} is too long, reduce to less than 63'
                    ' characters',
                    errno.ENAMETOOLONG
                )
            if vm_instance and any(
                d.get('attributes', {}).get('path') == path and d['id'] != device.get('id')
                for d in vm_instance['devices'] if d['dtype'] == 'DISK'
            ):
                verrors.add(
                    'attributes.path',
                    f'{vm_instance["name"]} has "{path}" already configured'
                )
        elif device.get('dtype') == 'RAW':
            path = device['attributes'].get('path')
            exists = device['attributes'].get('exists', True)
            if not path:
                verrors.add('attributes.path', 'Path is required.')
            else:
                if exists and not os.path.exists(path):
                    verrors.add('attributes.path', 'Path must exist.')
                if not exists:
                    if os.path.exists(path):
                        verrors.add('attributes.path', 'Path must not exist.')
                    elif not device['attributes'].get('size'):
                        verrors.add('attributes.size', 'Please provide a valid size for the raw file.')
                if (
                    old and old['attributes'].get('size') != device['attributes'].get('size') and
                    not device['attributes'].get('size')
                ):
                    verrors.add('attributes.size', 'Please provide a valid size for the raw file.')
                await check_path_resides_within_volume(
                    verrors, self.middleware, 'attributes.path', path,
                )
                if vm_instance and exists and any(
                    d.get('attributes', {}).get('path') == path and d['id'] != device.get('id')
                    for d in vm_instance['devices'] if d['dtype'] == 'RAW'
                ):
                    verrors.add(
                        'attributes.path',
                        f'{vm_instance["name"]} has "{path}" already configured'
                    )
        elif device.get('dtype') == 'CDROM':
            path = device['attributes'].get('path')
            if not path:
                verrors.add('attributes.path', 'Path is required.')
        elif device.get('dtype') == 'NIC':
            nic = device['attributes'].get('nic_attach')
            if nic:
                nic_choices = await self.middleware.call('vm.device.nic_attach_choices')
                if nic not in nic_choices:
                    verrors.add('attributes.nic_attach', 'Not a valid choice.')
        elif device.get('dtype') == 'VNC':
            if vm_instance and vm_instance['bootloader'] != 'UEFI':
                verrors.add('dtype', 'VNC only works with UEFI bootloader.')

        if verrors:
            raise verrors

        return device


async def kmod_load():
    kldstat = (await (await Popen(['/sbin/kldstat'], stdout=subprocess.PIPE)).communicate())[0].decode()
    if 'vmm.ko' not in kldstat:
        await Popen(['/sbin/kldload', 'vmm'])
    if 'nmdm.ko' not in kldstat:
        await Popen(['/sbin/kldload', 'nmdm'])


async def __event_system_ready(middleware, event_type, args):
    """
    Method called when system is ready, supposed to start VMs
    flagged that way.
    """
    if args['id'] != 'ready':
        return

    global ZFS_ARC_MAX_INITIAL
    ZFS_ARC_MAX_INITIAL = sysctl.filter('vfs.zfs.arc.max')[0].value

    for vm in await middleware.call('vm.query', [('autostart', '=', True)]):
        await middleware.call('vm.start', vm['id'])


class VMFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'vm'
    title = 'VM'

    async def query(self, path, enabled):
        vms_attached = []
        for device in await self.middleware.call('datastore.query', 'vm.device'):
            if device['dtype'] not in ('DISK', 'RAW'):
                continue

            disk = device['attributes'].get('path', None)
            if not disk:
                continue

            disk = re.sub(r'^/dev/zvol', '/mnt', disk)

            if is_child(disk, path):
                vm = {
                    'id': device['vm'].get('id'),
                    'name': device['vm'].get('name'),
                }
                if vm not in vms_attached:
                    vms_attached.append(vm)

        return vms_attached

    async def get_attachment_name(self, attachment):
        return attachment['name']

    async def delete(self, attachments):
        for attachment in attachments:
            try:
                await self.middleware.call('vm.stop', attachment['id'])
            except Exception:
                self.middleware.logger.warning('Unable to vm.stop %r', attachment['id'])

    async def toggle(self, attachments, enabled):
        for attachment in attachments:
            action = 'vm.start' if enabled else 'vm.stop'
            try:
                await self.middleware.call(action, attachment['id'])
            except Exception:
                self.middleware.logger.warning('Unable to %s %r', action, attachment['id'])


def setup(middleware):
    global ZFS_ARC_MAX_INITIAL
    ZFS_ARC_MAX_INITIAL = sysctl.filter('vfs.zfs.arc.max')[0].value
    asyncio.ensure_future(kmod_load())
    asyncio.ensure_future(middleware.call('pool.dataset.register_attachment_delegate',
                                          VMFSAttachmentDelegate(middleware)))
    middleware.event_subscribe('system', __event_system_ready)
