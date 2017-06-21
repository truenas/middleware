from middlewared.schema import accepts, Int, Str, Dict, List, Bool, Patch
from middlewared.service import filterable, CRUDService, item_method, private
from middlewared.utils import Nid, Popen

import asyncio
import errno
import netif
import os
import random
import stat
import subprocess
import sysctl


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

    async def stop(self, id):
        supervisor = self._vm.get(id)
        if not supervisor:
            return False

        err = await supervisor.stop()
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


class VMSupervisor(object):

    def __init__(self, manager, vm):
        self.manager = manager
        self.logger = self.manager.logger
        self.vm = vm
        self.proc = None
        self.taps = []
        self.bhyve_error = None

    async def run(self):
        args = [
            'bhyve',
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
        for device in self.vm['devices']:
            if device['dtype'] == 'DISK' or device['dtype'] == 'RAW':
                if device['attributes'].get('type') == 'AHCI':
                    args += ['-s', '{},ahci-hd,{}'.format(nid(), device['attributes']['path'])]
                else:
                    args += ['-s', '{},virtio-blk,{}'.format(nid(), device['attributes']['path'])]
            elif device['dtype'] == 'CDROM':
                args += ['-s', '{},ahci-cd,{}'.format(nid(), device['attributes']['path'])]
            elif device['dtype'] == 'NIC':
                tapname = netif.create_interface('tap')
                tap = netif.get_interface(tapname)
                tap.up()
                self.taps.append(tapname)
                # If Bridge
                if True:
                    bridge = None
                    for name, iface in list(netif.list_interfaces().items()):
                        if name.startswith('bridge'):
                            bridge = iface
                            break
                    if not bridge:
                        bridge = netif.get_interface(netif.create_interface('bridge'))

                    if bridge.mtu > tap.mtu:
                        self.logger.debug("===> Set tap(4) mtu to {0} like in bridge(4) mtu {1}".format(tap.mtu, bridge.mtu))
                        tap.mtu = bridge.mtu

                    bridge.add_member(tapname)

                    defiface = (await (await Popen("route -nv show default|grep -w interface|awk '{ print $2 }'", stdout=subprocess.PIPE, shell=True)).communicate())[0].strip().decode()
                    if defiface and defiface not in bridge.members:
                        bridge.add_member(defiface)
                    bridge.up()
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
                    args += ['-s', '{},{},{},mac={}'.format(nid(), nictype, tapname, self.random_mac())]
                else:
                    args += ['-s', '{},{},{},mac={}'.format(nid(), nictype, tapname, mac_address)]
            elif device['dtype'] == 'VNC':
                if device['attributes'].get('wait'):
                    wait = 'wait'
                else:
                    wait = ''

                vnc_resolution = device['attributes'].get('vnc_resolution', None)
                vnc_port = int(device['attributes'].get('vnc_port', 5900 + self.vm['id']))

                if vnc_resolution is None:
                    args += [
                        '-s', '29,fbuf,tcp=0.0.0.0:{},w=1024,h=768,{}'.format(vnc_port, wait),
                        '-s', '30,xhci,tablet',
                    ]
                else:
                    vnc_resolution = vnc_resolution.split('x')
                    width = vnc_resolution[0]
                    height = vnc_resolution[1]
                    args += [
                        '-s', '29,fbuf,tcp=0.0.0.0:{},w={},h={},{}'.format(vnc_port, width, height, wait),
                        '-s', '30,xhci,tablet',
                    ]

        args.append(self.vm['name'])

        self.logger.debug('Starting bhyve: {}'.format(' '.join(args)))
        self.proc = await Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

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
            await self.destroy_vm()
        elif self.bhyve_error in (2, 3):
            self.logger.info("===> Stopping VM: {0} ID: {1} BHYVE_CODE: {2}".format(self.vm['name'], self.vm['id'], self.bhyve_error))
            await self.manager.stop(self.vm['id'])
        elif self.bhyve_error not in (0, 1, 2, 3, None):
            self.logger.info("===> Error VM: {0} ID: {1} BHYVE_CODE: {2}".format(self.vm['name'], self.vm['id'], self.bhyve_error))
            await self.destroy_vm()

    async def destroy_vm(self):
        self.logger.warn("===> Destroying VM: {0} ID: {1} BHYVE_CODE: {2}".format(self.vm['name'], self.vm['id'], self.bhyve_error))
        # XXX: We need to catch the bhyvectl return error.
        bhyve_error = await (await Popen(['bhyvectl', '--destroy', '--vm={}'.format(self.vm['name'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE)).wait()
        self.manager._vm.pop(self.vm['id'], None)
        self.destroy_tap()

    def destroy_tap(self):
        while self.taps:
            netif.destroy_interface(self.taps.pop())

    def random_mac(self):
        mac_address = [0x00, 0xa0, 0x98, random.randint(0x00, 0x7f), random.randint(0x00, 0xff), random.randint(0x00, 0xff)]
        return ':'.join(map(lambda x: "%02x" % x, mac_address))

    async def kill_bhyve_pid(self):
        if self.proc:
            try:
                os.kill(self.proc.pid, 15)
            except ProcessLookupError as e:
                # Already stopped, process do not exist anymore
                if e.errno != errno.ESRCH:
                    raise

            await self.destroy_vm()
            return True

    async def restart(self):
        bhyve_error = await (await Popen(['bhyvectl', '--force-reset', '--vm={}'.format(self.vm['name'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE)).wait()
        self.logger.debug("==> Reset VM: {0} ID: {1} BHYVE_CODE: {2}".format(self.vm['name'], self.vm['id'], bhyve_error))
        self.destroy_tap()

    async def stop(self):
        bhyve_error = await (await Popen(['bhyvectl', '--force-poweroff', '--vm={}'.format(self.vm['name'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE)).wait()
        self.logger.debug("===> Stopping VM: {0} ID: {1} BHYVE_CODE: {2}".format(self.vm['name'], self.vm['id'], self.bhyve_error))

        if bhyve_error:
            self.logger.error("===> Stopping VM error: {0}".format(bhyve_error))

        return await self.kill_bhyve_pid()

    async def running(self):
        bhyve_error = await (await Popen(['bhyvectl', '--vm={}'.format(self.vm['name'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE)).wait()
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


class VMService(CRUDService):

    class Config:
        namespace = 'vm'

    def __init__(self, *args, **kwargs):
        super(VMService, self).__init__(*args, **kwargs)
        self._manager = VMManager(self)

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

    @accepts(Dict(
        'vm_create',
        Str('name'),
        Str('description'),
        Int('vcpus'),
        Int('memory'),
        Str('bootloader'),
        List('devices'),
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

    @private
    async def do_update_devices(self, id, devices):
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
            update_devices = await self.do_update_devices(id, devices)
        if data:
            return await self.middleware.call('datastore.update', 'vm.vm', id, data)
        else:
            return update_devices

    @accepts(Int('id'),
        Dict('devices', additional_attrs=True),
    )
    async def create_device(self, id, data):
        """Create a new device in an existing vm."""
        devices_type = ('NIC', 'DISK', 'CDROM', 'VNC')
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
        return await self.middleware.call('datastore.delete', 'vm.vm', id)

    @item_method
    @accepts(Int('id'))
    async def start(self, id):
        """Start a VM."""
        return await self._manager.start(id)

    @item_method
    @accepts(Int('id'))
    async def stop(self, id):
        """Stop a VM."""
        return await self._manager.stop(id)

    @item_method
    @accepts(Int('id'))
    async def restart(self, id):
        """Restart a VM."""
        return await self._manager.restart(id)

    @item_method
    @accepts(Int('id'))
    async def status(self, id):
        """Get the status of a VM, if it is RUNNING or STOPPED."""
        return await self._manager.status(id)


async def kmod_load():
    kldstat = (await (await Popen(['/sbin/kldstat'], stdout=subprocess.PIPE)).communicate())[0].decode()
    if 'vmm.ko' not in kldstat:
        await Popen(['/sbin/kldload', 'vmm'])
    if 'nmdm.ko' not in kldstat:
        await Popen(['/sbin/kldload', 'nmdm'])


async def _event_system_ready(middleware, event_type, args):
    """
    Method called when system is ready, supposed to start VMs
    flagged that way.
    """
    if args['id'] != 'ready':
        return

    for vm in await middleware.call('vm.query', [('autostart', '=', True)]):
        await middleware.call('vm.start', vm['id'])


def setup(middleware):
    asyncio.ensure_future(kmod_load())
    middleware.event_subscribe('system', _event_system_ready)
