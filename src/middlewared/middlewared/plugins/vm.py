from middlewared.schema import accepts, Int, Str, Dict, List, Bool, Patch
from middlewared.service import filterable, CRUDService, item_method, private, job, CallError
from middlewared.utils import Nid, Popen
from urllib.request import urlretrieve
from pipes import quote

import middlewared.logger
import asyncio
import errno
import netif
import os
import os.path
import random
import stat
import subprocess
import sysctl
import gzip
import hashlib
import shutil
import signal

logger = middlewared.logger.Logger('vm').getLogger()

CONTAINER_IMAGES = {
    "RancherOS": {
        "URL": "http://download.freenas.org/bhyve-templates/rancheros-bhyve-v1.1.3/rancheros-bhyve-v1.1.3.img.gz",
        "GZIPFILE": "rancheros-bhyve-v1.1.3.img.gz",
        "SHA256": "e9288df573e01f5468c1f7e4609fbeab481caa3ffc5855af9d003b49557dde84",
    }
}
BUFSIZE = 65536
ZFS_ARC_MAX = 0


class VMManager(object):

    def __init__(self, service):
        self.service = service
        self.logger = self.service.logger
        self._vm = {}

    async def start(self, id):
        vm = await self.service.query([('id', '=', id)], {'get': True})
        self._vm[id] = VMSupervisor(self, vm)
        try:
            asyncio.ensure_future(self._vm[id].run())
            return True
        except:
            raise

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
        if supervisor is None:
            vm = await self.service.query([('id', '=', id)], {'get': True})
            self._vm[id] = VMSupervisor(self, vm)
            supervisor = self._vm.get(id)

        if supervisor and await supervisor.running():
            return {
                'state': 'RUNNING',
            }
        else:
            return {
                'state': 'STOPPED',
            }

    async def clone(self, id):
        try:
            vm = await self.service.query([('id', '=', id)], {'get': True})
            return vm
        except IndexError:
            self.logger.error("VM does not exist.")
            return None


class VMSupervisor(object):

    def __init__(self, manager, vm):
        self.manager = manager
        self.logger = self.manager.logger
        self.middleware = self.manager.service.middleware
        self.vm = vm
        self.proc = None
        self.grub_proc = None
        self.web_proc = None
        self.taps = []
        self.bhyve_error = None
        self.vmutils = VMUtils

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

        nid = Nid(3)
        device_map_file = None
        grub_dir = None
        grub_boot_device = False
        for device in self.vm['devices']:
            if device['dtype'] == 'DISK' or device['dtype'] == 'RAW':

                disk_sector_size = device['attributes'].get('sectorsize', 0)
                if disk_sector_size > 0:
                    sectorsize_args = ",sectorsize=" + str(disk_sector_size)
                else:
                    sectorsize_args = ""

                if device['attributes'].get('type') == 'AHCI':
                    args += ['-s', '{},ahci-hd,{}{}'.format(nid(), device['attributes']['path'], sectorsize_args)]
                else:
                    args += ['-s', '{},virtio-blk,{}{}'.format(nid(), device['attributes']['path'], sectorsize_args)]

                if self.vmutils.is_container(self.vm) and \
                    device['attributes'].get('boot', False) is True and \
                        grub_boot_device is False:
                    shared_fs = await self.middleware.call('vm.get_sharefs')
                    device_map_file = self.vmutils.ctn_device_map(shared_fs, self.vm['id'], self.vm['name'], device)
                    grub_dir = self.vmutils.ctn_grub(shared_fs, self.vm['id'], self.vm['name'], device, device['attributes'].get('rootpwd', None), None)
                    grub_boot_device = True
                    self.logger.debug("==> Boot Disk: {0}".format(device))

            elif device['dtype'] == 'CDROM':
                args += ['-s', '{},ahci-cd,{}'.format(nid(), device['attributes']['path'])]
            elif device['dtype'] == 'NIC':
                attach_iface = device['attributes'].get('nic_attach')

                self.logger.debug('====> NIC_ATTACH: {0}'.format(attach_iface))

                tapname = netif.create_interface('tap')
                tap = netif.get_interface(tapname)
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
                if mac_address == "":
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
                vnc_port = int(device['attributes'].get('vnc_port', 5900 + self.vm['id']))
                vnc_bind = device['attributes'].get('vnc_bind', '0.0.0.0')
                vnc_password = device['attributes'].get('vnc_password', None)
                vnc_web = device['attributes'].get('vnc_web', None)

                vnc_password_args = ""
                if vnc_password:
                    vnc_password_args = "password=" + vnc_password

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

        # grub-bhyve support for containers
        if self.vmutils.is_container(self.vm):
            grub_bhyve_args = [
                'grub-bhyve', '-m', device_map_file,
                '-r', 'host',
                '-M', str(self.vm['memory']),
                '-d', grub_dir,
                str(self.vm['id']) + '_' + self.vm['name'],
            ]

            #  If container has no boot device, we should stop.
            if grub_boot_device is False:
                self.logger.error("===> There is no boot disk for vm: {0}".format(self.vm['name']))
                return False

            self.logger.debug('Starting grub-bhyve: {}'.format(' '.join(grub_bhyve_args)))
            self.grub_proc = await Popen(grub_bhyve_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            while True:
                line = await self.grub_proc.stdout.readline()
                if line == b'':
                    break

        args.append(str(self.vm['id']) + '_' + self.vm['name'])

        self.logger.debug('Starting bhyve: {}'.format(' '.join(args)))
        self.proc = await Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        if vnc_web:
            split_port = int(str(vnc_port)[:2]) - 1
            vnc_web_port = str(split_port) + str(vnc_port)[2:]

            web_bind = ':{}'.format(vnc_web_port) if vnc_bind is '0.0.0.0' else '{}:{}'.format(vnc_bind, vnc_web_port)

            self.web_proc = await Popen(['/usr/local/libexec/novnc/utils/websockify/run', '--web',
                                         '/usr/local/libexec/novnc/', '--wrap-mode=ignore',
                                         web_bind, '{}:{}'.format(vnc_bind, vnc_port)],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.logger.debug("==> Start WEBVNC at port {} with pid number {}".format(vnc_web_port, self.web_proc.pid))

        while True:
            line = await self.proc.stdout.readline()
            if line == b'':
                break
            self.logger.debug('{}: {}'.format(self.vm['name'], line.decode()))

        # bhyve returns the following status code:
        # 0 - VM has been reset
        # 1 - VM has been powered off
        # 2 - VM has been halted
        # 3 - VM generated a triple fault
        # all other non-zero status codes are errors
        self.bhyve_error = await self.proc.wait()
        if self.bhyve_error == 0:
            self.logger.info("===> Rebooting VM: {0} ID: {1} BHYVE_CODE: {2}".format(self.vm['name'], self.vm['id'], self.bhyve_error))
            await self.manager.restart(self.vm['id'])
            await self.manager.start(self.vm['id'])
        elif self.bhyve_error == 1:
            # XXX: Need a better way to handle the vmm destroy.
            self.logger.info("===> Powered off VM: {0} ID: {1} BHYVE_CODE: {2}".format(self.vm['name'], self.vm['id'], self.bhyve_error))
            await self.__teardown_guest_vmemory(self.vm['id'])
            await self.destroy_vm()
        elif self.bhyve_error in (2, 3):
            self.logger.info("===> Stopping VM: {0} ID: {1} BHYVE_CODE: {2}".format(self.vm['name'], self.vm['id'], self.bhyve_error))
            await self.__teardown_guest_vmemory(self.vm['id'])
            await self.manager.stop(self.vm['id'])
        elif self.bhyve_error not in (0, 1, 2, 3, None):
            self.logger.info("===> Error VM: {0} ID: {1} BHYVE_CODE: {2}".format(self.vm['name'], self.vm['id'], self.bhyve_error))
            await self.__teardown_guest_vmemory(self.vm['id'])
            await self.destroy_vm()

    async def destroy_vm(self):
        self.logger.warn("===> Destroying VM: {0} ID: {1} BHYVE_CODE: {2}".format(self.vm['name'], self.vm['id'], self.bhyve_error))
        # XXX: We need to catch the bhyvectl return error.
        await (await Popen(['bhyvectl', '--destroy', '--vm={}'.format(str(self.vm['id']) + '_' + self.vm['name'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE)).wait()
        self.manager._vm.pop(self.vm['id'], None)
        await self.kill_bhyve_web()
        self.destroy_tap()

    async def __teardown_guest_vmemory(self, id):
        guest_status = await self.middleware.call('vm.status', id)
        vm = await self.middleware.call('datastore.query', 'vm.vm', [('id', '=', id)])
        guest_memory = vm[0].get('memory', None) * 1024 * 1024
        max_arc = sysctl.filter('vfs.zfs.arc_max')
        resize_arc = max_arc[0].value + guest_memory

        if guest_status.get('state') == "STOPPED":
            if resize_arc <= ZFS_ARC_MAX:
                sysctl.filter('vfs.zfs.arc_max')[0].value = max_arc[0].value + guest_memory
                self.logger.debug("===> Give back guest memory to ARC.: {}".format(guest_memory))
            elif resize_arc > ZFS_ARC_MAX and max_arc[0].value < ZFS_ARC_MAX:
                sysctl.filter('vfs.zfs.arc_max')[0].value = ZFS_ARC_MAX
                self.logger.debug("===> Enough guest memory to set ARC back to its original limit.")
            return True
        return False

    def destroy_tap(self):
        while self.taps:
            netif.destroy_interface(self.taps.pop())

    def set_iface_mtu(self, ifacesrc, ifacedst):
        ifacedst.mtu = ifacesrc.mtu

        return ifacedst

    async def bridge_setup(self, tapname, tap, attach_iface):
        if_bridge = []
        bridge_enabled = False

        if attach_iface is None:
            # XXX: backward compatibility prior to 11.1-RELEASE.
            try:
                attach_iface = netif.RoutingTable().default_route_ipv4.interface
                attach_iface_info = netif.get_interface(attach_iface)
            except:
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

        if if_bridge:
            for bridge in if_bridge:
                if attach_iface in bridge.members:
                    bridge_enabled = True
                    self.set_iface_mtu(attach_iface_info, tap)
                    bridge.add_member(tapname)
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
                self.logger.debug("==> Killing WEBVNC: {}".format(self.web_proc.pid))
                os.kill(self.web_proc.pid, signal.SIGTERM)
            except ProcessLookupError as e:
                if e.errno != errno.ESRCH:
                    raise
            return True

    async def restart(self):
        bhyve_error = await (await Popen(['bhyvectl', '--force-reset', '--vm={}'.format(str(self.vm['id']) + '_' + self.vm['name'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE)).wait()
        self.logger.debug("==> Reset VM: {0} ID: {1} BHYVE_CODE: {2}".format(self.vm['name'], self.vm['id'], bhyve_error))
        self.destroy_tap()
        await self.kill_bhyve_web()

    async def stop(self, force=False):
        if force:
            bhyve_error = await (await Popen(['bhyvectl', '--force-poweroff', '--vm={}'.format(str(self.vm['id']) + '_' + self.vm['name'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE)).wait()
            self.logger.debug("===> Force Stop VM: {0} ID: {1} BHYVE_CODE: {2}".format(self.vm['name'], self.vm['id'], self.bhyve_error))
            if bhyve_error:
                self.logger.error("===> Stopping VM error: {0}".format(bhyve_error))
        else:
            os.kill(self.proc.pid, signal.SIGTERM)
            self.logger.debug("===> Soft Stop VM: {0} ID: {1} BHYVE_CODE: {2}".format(self.vm['name'], self.vm['id'], self.bhyve_error))

        self.destroy_tap()
        return await self.kill_bhyve_pid()

    async def running(self):
        bhyve_error = await (await Popen(['bhyvectl', '--vm={}'.format(str(self.vm['id']) + '_' + self.vm['name'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE)).wait()
        if bhyve_error == 0:
            if self.proc:
                try:
                    os.kill(self.proc.pid, 0)
                except OSError:
                    self.logger.error("===> VMM {0} is running without bhyve process.".format(self.vm['name']))
                    return False
                return True
            else:
                # XXX: We return true for now to keep the vm.status sane.
                # It is necessary handle in a better way the bhyve process associated with the vmm.
                return True
        elif bhyve_error == 1:
            return False


class VMUtils(object):

    def is_container(data):
        if data:
            if data.get('vm_type', None) == 'Container Provider':
                return True
        else:
            return False

    def is_gzip(file_path):
        """Check if it is a gzip file and not empty"""
        with gzip.open(file_path, 'rb') as gfile:
            try:
                gf_content = gfile.read(1)
                if len(gf_content) > 0:
                    return True
            except:
                return False

    @staticmethod
    def __mkdirs(path):
        if not os.path.exists(os.path.dirname(path)):
            try:
                os.makedirs(path)
                return True
            except OSError as err:
                if err.errno != errno.EEXIST:
                    raise

    def do_dirtree_container(sharefs_path):
        iso_path = sharefs_path + '/iso_files/'
        cnt_config_path = sharefs_path + '/configs/'

        VMUtils.__mkdirs(iso_path)
        VMUtils.__mkdirs(cnt_config_path)

    def ctn_device_map(sharefs_path, vm_id, vm_name, disk):
        vm_private_dir = sharefs_path + '/configs/' + str(vm_id) + '_' + vm_name + '/'
        config_file = vm_private_dir + 'device.map'

        VMUtils.__mkdirs(vm_private_dir)

        with open(config_file, 'w') as dmap:
            if disk['attributes']['boot'] is True:
                dmap.write('(hd0) {0}'.format(disk['attributes']['path']))

        return config_file

    def ctn_grub(sharefs_path, vm_id, vm_name, disk, password, vmOS=None):
        if vmOS is None:
            vmOS = 'RancherOS'

        grub_default_args = [
            'set timeout=0',
            'set default={}'.format(vmOS),
            'menuentry "bhyve-image" --id %s {' % (vmOS),
            'set root=(hd0,msdos1)',
        ]

        grub_additional_args = {
            "RancherOS": ['linux /boot/vmlinuz-4.9.75-rancher rancher.password={0} printk.devkmsg=on rancher.state.dev=LABEL=RANCHER_STATE rancher.state.wait rancher.resize_device=/dev/sda'.format(quote(password)),
                          'initrd /boot/initrd-v1.1.3']
        }

        vm_private_dir = sharefs_path + '/configs/' + str(vm_id) + '_' + vm_name + '/' + 'grub/'
        grub_file = vm_private_dir + 'grub.cfg'

        VMUtils.__mkdirs(vm_private_dir)

        if not os.path.exists(grub_file):
            with open(grub_file, 'w') as grubcfg:
                for line in grub_default_args:
                    grubcfg.write(line)
                    grubcfg.write('\n')
                for line in grub_additional_args[vmOS]:
                    grubcfg.write(line)
                    grubcfg.write('\n')
                grubcfg.write('}')
        else:
            grub_password = 'rancher.password={0}'.format(quote(password))

            with open(grub_file, 'r') as cfg_src:
                cfg_src_data = cfg_src.read()
                src_data = cfg_src_data.split(' ')
                for index, data in enumerate(src_data):
                    if data.startswith('rancher.password'):
                        if src_data[index] == grub_password:
                            return vm_private_dir
                        src_data[index] = 'rancher.password={0}'.format(quote(password))
                        break

            with open(grub_file, 'w') as cfg_dst:
                cfg_dst.write(" ".join(src_data))

        return vm_private_dir

    def check_sha256(file_path, vmOS):
        vm_os = CONTAINER_IMAGES.get(vmOS)
        digest_sha256 = vm_os['SHA256']

        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(BUFSIZE)
                if not data:
                    break
                sha256.update(data)

        if sha256.hexdigest() == digest_sha256:
            return True
        else:
            return False


class VMService(CRUDService):

    class Config:
        namespace = 'vm'

    def __init__(self, *args, **kwargs):
        super(VMService, self).__init__(*args, **kwargs)
        self._manager = VMManager(self)
        self.vmutils = VMUtils

    @accepts()
    def flags(self):
        """Returns a dictionary with CPU flags for bhyve."""
        data = {}

        vmx = sysctl.filter('hw.vmm.vmx.initialized')
        data['intel_vmx'] = True if vmx and vmx[0].value else False

        ug = sysctl.filter('hw.vmm.vmx.cap.unrestricted_guest')
        data['unrestricted_guest'] = True if ug and ug[0].value else False

        rvi = sysctl.filter('hw.vmm.svm.features')
        data['amd_rvi'] = True if rvi and rvi[0].value != 0 else False

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

    @filterable
    async def query(self, filters=None, options=None):
        options = options or {}
        options['extend'] = 'vm._extend_vm'
        return await self.middleware.call('datastore.query', 'vm.vm', filters, options)

    async def _extend_vm(self, vm):
        vm['devices'] = []
        for device in await self.middleware.call('datastore.query', 'vm.device', [('vm__id', '=', vm['id'])]):
            device.pop('id', None)
            device.pop('vm', None)
            vm['devices'].append(device)
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
                    vnc_attr = {"vnc_port": vnc_port, "vnc_web": vnc_web}
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
        ifaces_dict_list = self.middleware.call_sync('interfaces.ip_in_use', {'ipv4': True})
        ifaces = [alias_dict['address'] for alias_dict in ifaces_dict_list]

        default_ifaces.extend(ifaces)
        return default_ifaces

    @accepts(Str('pool'),
             Bool('stop', default=False),)
    async def stop_by_pool(self, pool, stop):
        """
        Get all guests attached to a given pool, if set stop True, it will stop the guests.

        Returns:
            dict: will return a dict with vm_id, vm_name, device_id and disk path.
        """
        vms_attached = []
        if pool:
            devices = await self.middleware.call('datastore.query', 'vm.device')
            for device in devices:
                if device['dtype'] == 'DISK' or device['dtype'] == 'RAW':
                        disk = device['attributes'].get('path', None)
                        if device['dtype'] == 'DISK':
                            disk = disk.lstrip('/dev/zvol/').split('/')[0]
                        elif device['dtype'] == 'RAW':
                            disk = disk.lstrip('/mnt/').split('/')[0]

                        if disk == pool:
                            status = await self.status(device['vm'].get('id'))
                            vms_attached.append({'vm_id': device['vm'].get('id'), 'vm_name': device['vm'].get('name'),
                                                 'device_id': device.get('id'), 'vm_disk': device['attributes'].get('path', None)})
                            if stop:
                                if status.get('state') == 'RUNNING':
                                    await self.stop(device['vm'].get('id'))
        return vms_attached

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
        except:
            guest_status = None

        if guest_status and guest_status['state'] == 'RUNNING':
            device = "/dev/nmdm{0}B".format(id)
            if stat.S_ISCHR(os.stat(device).st_mode) is True:
                    return device

        return False

    @private
    def __activate_sharefs(self, dataset):
        pool_exist = False
        images_fs = '/.bhyve_containers'
        new_fs = dataset + images_fs

        if self.middleware.call_sync('zfs.dataset.query', [('id', '=', new_fs)]):
            pool_exist = True

        if pool_exist is False:
            try:
                self.logger.debug("===> Trying to create: {0}".format(new_fs))
                self.middleware.call_sync('zfs.dataset.create', {
                    'name': new_fs,
                    'type': 'FILESYSTEM',
                    'properties': {'sparse': False},
                })
            except Exception as e:
                self.logger.error("Failed to create dataset", exc_info=True)
                raise e
            self.middleware.call_sync('zfs.dataset.mount', new_fs)
            mountpoint = self.middleware.call_sync('zfs.dataset.query', [('id', '=', new_fs)])[0]['mountpoint']
            self.vmutils.do_dirtree_container(mountpoint)
            return True
        else:
            return False

    @accepts(Str('pool_name'))
    def activate_sharefs(self, pool_name=None):
        """
        Create a pool for pre built containers images.
        """

        if pool_name:
            return self.__activate_sharefs(pool_name)
        else:
            # Only to keep compatibility with the OLD GUI
            blocked_pools = ['freenas-boot']
            pool_name = None

            # We get the first available pool.
            for pool in self.middleware.call_sync('zfs.pool.query'):
                if pool['name'] not in blocked_pools:
                    pool_name = pool['name']
                    break
            if pool_name:
                return self.__activate_sharefs(pool_name)
            else:
                self.logger.error("===> There is no pool available to activate a shared fs.")
                return False

    @accepts()
    async def get_sharefs(self):
        """
        Return the shared pool for containers images.
        """
        for dataset in await self.middleware.call('zfs.dataset.query'):
            if '.bhyve_containers' in dataset['name']:
                return dataset['mountpoint']
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

    async def __set_guest_vmemory(self, memory):
        usermem = sysctl.filter('hw.usermem')
        max_arc = sysctl.filter('vfs.zfs.arc_max')
        guest_mem_used = await self.get_vmemory_in_use()
        memory = memory * 1024 * 1024

        # Keep at least 35% of memory from initial arc_max.
        throttled_arc_max = int(usermem[0].value * 1.35) - usermem[0].value
        # Get the user memory and keep space for ARC.
        throttled_user_mem = int(usermem[0].value - throttled_arc_max)
        # Potential memory used by guests.
        memory_used = guest_mem_used['RPRD'] + guest_mem_used['RNP']

        vms_memory = memory_used + memory
        if vms_memory <= throttled_user_mem:
            if max_arc[0].value > throttled_arc_max:
                if max(max_arc[0].value - memory, 0) != 0:
                    self.logger.info("===> Setting ARC FROM: {} TO: {}".format(max_arc[0].value, max_arc[0].value - memory))
                    sysctl.filter('vfs.zfs.arc_max')[0].value = max_arc[0].value - memory
            return True
        else:
            return False

    async def __init_guest_vmemory(self, id):
        vm = await self.middleware.call('datastore.query', 'vm.vm', [('id', '=', id)])
        guest_memory = vm[0].get('memory', None)
        guest_status = await self.status(id)
        if guest_status.get('state') != "RUNNING":
            setvmem = await self.__set_guest_vmemory(guest_memory)
            if setvmem is False:
                self.logger.warn("===> Cannot guarantee memory for guest id: {}".format(id))
            return setvmem

        else:
            self.logger.debug("===> bhyve process is running, we won't allocate memory")
            return False

    @accepts(Int('id'))
    async def rm_container_conf(self, id):
        vm_data = await self.middleware.call('datastore.query', 'vm.vm', [('id', '=', id)])
        if vm_data:
            sharefs = await self.middleware.call('vm.get_sharefs')
            if sharefs:
                cnt_conf_name = str(vm_data[0].get('id')) + '_' + vm_data[0].get('name')
                full_path = sharefs + '/configs/' + cnt_conf_name
                if os.path.exists(full_path):
                    shutil.rmtree(full_path)
                    return True
        return False

    @accepts(Str('raw_path'), Str('size'))
    async def raw_resize(self, raw_path, size=0):
        unit_size = ('M', 'G', 'T')
        truncate_cmd = [
            'truncate', '-s',
        ]
        if size is 0:
            return False
        if os.path.exists(raw_path):
            if size is 0:
                return False
            expand_size = size if len(size) > 0 and size[-1:] in unit_size else size + 'G'
            truncate_cmd += [expand_size, raw_path]
            self.logger.debug('===> DISK: {0} resize to: {1}'.format(raw_path, expand_size))
            error = await (await Popen(truncate_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)).wait()
            if error:
                self.logger.debug("===> Error to resize disk: {0} with size: {1}".format(raw_path, expand_size))
                return False
            else:
                return True
        else:
            return False

    @accepts()
    def random_mac(self):
        """ Create a random mac address.

            Returns:
                str: with six groups of two hexadecimal digits
        """
        mac_address = [0x00, 0xa0, 0x98, random.randint(0x00, 0x7f), random.randint(0x00, 0xff), random.randint(0x00, 0xff)]
        return ':'.join(["%02x" % x for x in mac_address])

    @accepts(Dict(
        'vm_create',
        Str('name'),
        Str('description'),
        Int('vcpus'),
        Int('memory'),
        Str('bootloader'),
        List("devices"),
        Str('vm_type'),
        Bool('autostart'),
        register=True,
    ))
    async def do_create(self, data):
        """Create a VM."""

        devices = data.pop('devices')
        pk = await self.middleware.call('datastore.insert', 'vm.vm', data)

        for device in devices:
            device['vm'] = pk
            await self.middleware.call('datastore.insert', 'vm.device', device)
        return pk

    async def __do_update_devices(self, id, devices):
        if devices and isinstance(devices, list) is True:
            device_query = await self.middleware.call('datastore.query', 'vm.device', [('vm__id', '=', int(id))])

            # Make sure both list has the same size.
            if len(device_query) != len(devices):
                return False

            get_devices = []
            for q in device_query:
                q.pop('vm')
                get_devices.append(q)

            while len(devices) > 0:
                update_item = devices.pop(0)
                old_item = get_devices.pop(0)
                if old_item['dtype'] == update_item['dtype']:
                    old_item['attributes'] = update_item['attributes']
                    device_id = old_item.pop('id')
                    await self.middleware.call('datastore.update', 'vm.device', device_id, old_item)
            return True

    @accepts(Int('id'), Patch(
        'vm_create',
        'vm_update',
        ('attr', {'update': True}),
    ))
    async def do_update(self, id, data):
        """Update all information of a specific VM."""
        devices = data.pop('devices', None)
        if devices:
            update_devices = await self.__do_update_devices(id, devices)
        if data:
            return await self.middleware.call('datastore.update', 'vm.vm', id, data)
        else:
            return update_devices

    @accepts(Int('id'),
             Dict('devices', additional_attrs=True), )
    async def create_device(self, id, data):
        """Create a new device in an existing vm."""
        devices_type = ('NIC', 'DISK', 'CDROM', 'VNC', 'RAW')
        devices = data.get('devices', None)

        if devices:
            devices[0].update({"vm": id})
            dtype = devices[0].get('dtype', None)
            if dtype in devices_type and isinstance(devices, list) is True:
                devices = devices[0]
                await self.middleware.call('datastore.insert', 'vm.device', devices)
                return True
            else:
                return False
        else:
            return False

    @accepts(Int('id'))
    async def do_delete(self, id):
        """Delete a VM."""
        status = await self.status(id)
        if isinstance(status, dict):
            if status.get('state') == "RUNNING":
                await self.stop(id)
        try:
            vm_data = await self.middleware.call('datastore.query', 'vm.vm', [('id', '=', id)])
            if self.vmutils.is_container(vm_data[0]):
                await self.middleware.call('vm.rm_container_conf', id)
            return await self.middleware.call('datastore.delete', 'vm.vm', id)
        except Exception as err:
            self.logger.error("===> {0}".format(err))
            return False

    @item_method
    @accepts(Int('id'))
    async def start(self, id):
        """Start a VM."""
        try:
            if await self.__init_guest_vmemory(id):
                return await self._manager.start(id)
            else:
                return False
        except Exception as err:
            self.logger.error("===> {0}".format(err))
            return False

    @item_method
    @accepts(Int('id'), Bool('force', default=False),)
    async def stop(self, id, force):
        """Stop a VM."""
        try:
            return await self._manager.stop(id, force)
        except Exception as err:
            self.logger.error("===> {0}".format(err))
            return False

    @item_method
    @accepts(Int('id'))
    async def restart(self, id):
        """Restart a VM."""
        try:
            return await self._manager.restart(id)
        except Exception as err:
            self.logger.error("===> {0}".format(err))
            return False

    @item_method
    @accepts(Int('id'))
    async def status(self, id):
        """Get the status of a VM, if it is RUNNING or STOPPED."""
        try:
            return await self._manager.status(id)
        except Exception as err:
            self.logger.error("===> {0}".format(err))
            return False

    def fetch_hookreport(self, blocknum, blocksize, totalsize, job, file_name):
        """Hook to report the download progress."""
        readchunk = blocknum * blocksize
        if totalsize > 0:
            percent = readchunk * 1e2 / totalsize
            job.set_progress(int(percent), 'Downloading', {'downloaded': readchunk, 'total': totalsize})

    @accepts(Str('vmOS'), Bool('force', default=False))
    @job(lock='container')
    async def fetch_image(self, job, vmOS, force=False):
        """Download a pre-built image for bhyve"""
        vm_os = CONTAINER_IMAGES.get(vmOS)
        url = vm_os['URL']

        self.logger.debug("==> IMAGE: {0}".format(vm_os))

        sharefs = await self.middleware.call('vm.get_sharefs')
        vm_os_file = vm_os['GZIPFILE']
        iso_path = sharefs + '/iso_files/'
        file_path = iso_path + vm_os_file

        if os.path.exists(file_path) is False and force is False:
            logger.debug("===> Downloading: %s" % (url))
            await self.middleware.run_in_thread(lambda: urlretrieve(
                url,
                file_path,
                lambda nb, bs, fs, job=job: self.fetch_hookreport(nb, bs, fs, job, file_path)
            ))

    @accepts()
    async def list_images(self):
        return CONTAINER_IMAGES

    @accepts(Int('job_id'))
    async def get_download_status(self, job_id):
        """ Returns the status of the job, if job does not exists it returns False."""
        job_pool = await self.middleware.call('core.get_jobs', [('method', '=', 'vm.fetch_image')])
        for __job in job_pool:
            if __job['id'] == job_id:
                return __job
        return False

    @accepts(Str('vmOS'))
    async def image_path(self, vmOS):
        """Return the prebuilt image path or false in case it is not supported."""
        vm_os = CONTAINER_IMAGES.get(vmOS, None)
        if vm_os:
            image_file = vm_os['GZIPFILE']
            sharefs = await self.middleware.call('vm.get_sharefs')
            file_path = sharefs + '/iso_files/' + image_file
            if os.path.exists(file_path):
                if self.vmutils.check_sha256(file_path, vmOS):
                    self.logger.debug("===> Checksum OK: {}".format(file_path))
                    return file_path
                else:
                    self.logger.debug("===> Checksum NOK, removing file: {}".format(file_path))
                    os.remove(file_path)
                    return False
            else:
                return False
        else:
            return False

    @accepts(Str('src'), Str('dst'))
    def decompress_gzip(self, src, dst):
        if os.path.exists(dst):
            self.logger.error("===> DST: {0} exist, we stop here.".format(dst))
            return False

        if self.vmutils.is_gzip(src) is True:
            self.logger.debug("===> SRC: {0} DST: {1}".format(src, dst))
            with gzip.open(src, 'rb') as src_file, open(dst, 'wb') as dst_file:
                shutil.copyfileobj(src_file, dst_file)
            return True
        else:
            self.logger.error("===> SRC: {0} does not exists or is broken.".format(src))
            return False

    async def __find_clone(self, name):
        data = await self.middleware.call('vm.query', [], {'order_by': ['name']})
        clone_index = 0
        next_name = ""
        for vm_name in data:
            if name in vm_name['name'] and '_clone' in vm_name['name']:
                name_index = int(vm_name['name'][-1])
                next_name = vm_name['name'][:-1]
                if name_index >= clone_index:
                    clone_index = int(name_index) + 1

        if next_name:
            next_name = next_name + str(clone_index)
        else:
            next_name = name + '_clone' + str(clone_index)

        return next_name

    @accepts(Int('id'))
    async def clone(self, id):
        vm = await self._manager.clone(id)

        if vm is None:
            raise CallError('Cannot clone a VM that does not exist.', errno.EINVAL)

        origin_name = vm['name']
        del vm['id']

        vm['name'] = await self.__find_clone(vm['name'])

        for item in vm['devices']:
            if item['dtype'] == 'NIC':
                if 'mac' in item['attributes']:
                    del item['attributes']['mac']
            if item['dtype'] == 'VNC':
                if 'vnc_port' in item['attributes']:
                    del item['attributes']['vnc_port']
            if item['dtype'] == 'DISK':
                disk_src_path = '/'.join(item['attributes']['path'].split('/dev/zvol/')[-1:])
                disk_snapshot_name = vm['name']
                disk_snapshot_path = disk_src_path + '@' + disk_snapshot_name
                clone_dst_path = disk_src_path + '_' + vm['name']

                data = {'dataset': disk_src_path, 'name': disk_snapshot_name}
                await self.middleware.call('zfs.snapshot.create', data)

                data = {'snapshot': disk_snapshot_path, 'dataset_dst': clone_dst_path}
                await self.middleware.call('zfs.snapshot.clone', data)

                item['attributes']['path'] = '/dev/zvol/' + clone_dst_path
            if item['dtype'] == 'RAW':
                item['attributes']['path'] = ''
                self.logger.warn("For RAW disk you need copy it manually inside your NAS.")

        await self.create(vm)
        self.logger.info("VM cloned from {0} to {1}".format(origin_name, vm['name']))

        return True

    @accepts(Int('id'))
    async def get_vnc_web(self, id):
        """
            Get the VNC URL from a given VM.

            Returns:
                list: With all URL available.
        """
        vnc_web = []

        for vnc_device in await self.get_vnc(id):
            if vnc_device.get('vnc_web', None) is True:
                vnc_port = vnc_device.get('vnc_port', None)
                if vnc_port is None:
                    vnc_port = 5900 + id
                #  XXX: Create a method for web port.
                split_port = int(str(vnc_port)[:2]) - 1
                vnc_web_port = str(split_port) + str(vnc_port)[2:]
                bind_ip = vnc_device.get('vnc_bind', None)
                vnc_web.append('http://{}:{}/vnc_auto.html'.format(bind_ip, vnc_web_port))

        return vnc_web


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

    global ZFS_ARC_MAX
    max_arc = sysctl.filter('vfs.zfs.arc_max')
    ZFS_ARC_MAX = max_arc[0].value

    for vm in await middleware.call('vm.query', [('autostart', '=', True)]):
        await middleware.call('vm.start', vm['id'])


def setup(middleware):
    asyncio.ensure_future(kmod_load())
    middleware.event_subscribe('system', __event_system_ready)
