from middlewared.schema import accepts, Int, Str, Dict, List, Ref
from middlewared.service import CRUDService, job
from middlewared.utils import Nid, Popen
from middlewared.client import Client, CallTimeout
from urllib.request import urlretrieve

import middlewared.logger
import errno
import gevent
import netif
import os
import subprocess
import sysctl

logger = middlewared.logger.Logger('vm').getLogger()

CONTAINER_IMAGES = {
        "coreos": "https://stable.release.core-os.net/amd64-usr/current/coreos_production_image.bin.bz2",
    }

class VMManager(object):

    def __init__(self, service):
        self.service = service
        self.logger = self.service.logger
        self._vm = {}

    def start(self, id):
        vm = self.service.query([('id', '=', id)], {'get': True})
        self._vm[id] = VMSupervisor(self, vm)
        gevent.spawn(self._vm[id].run)

    def stop(self, id):
        supervisor = self._vm.get(id)
        if not supervisor:
            return False
        return supervisor.stop()

    def status(self, id):
        supervisor = self._vm.get(id)
        if supervisor and supervisor.running():
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
        self.vmutils = VMUtils

    def run(self):
        args = [
            'bhyve',
            '-A',
            '-P',
            '-H',
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

        if self.vmutils.is_container(self.vm) is True:
            logger.debug("====> RUNNING CONTAINER")

        nid = Nid(3)
        for device in self.vm['devices']:
            if device['dtype'] == 'DISK':
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
                    bridge.add_member(tapname)

                    defiface = Popen("route -nv show default|grep -w interface|awk '{ print $2 }'", stdout=subprocess.PIPE, shell=True).communicate()[0].strip()
                    if defiface and defiface not in bridge.members:
                        bridge.add_member(defiface)
                    bridge.up()
                if device['attributes'].get('type') == 'VIRTIO':
                    nictype = 'virtio-net'
                else:
                    nictype = 'e1000'
                args += ['-s', '{},{},{}'.format(nid(), nictype, tapname)]
            elif device['dtype'] == 'VNC':
                if device['attributes'].get('wait'):
                    wait = 'wait'
                else:
                    wait = ''

                vnc_port = int(device['attributes'].get('vnc_port', 5900 + self.vm['id']))

                args += [
                    '-s', '29,fbuf,tcp=0.0.0.0:{},w=1024,h=768,{}'.format(vnc_port, wait),
                    '-s', '30,xhci,tablet',
                ]

        args.append(self.vm['name'])

        self.logger.debug('Starting bhyve: {}'.format(' '.join(args)))
        self.proc = Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in self.proc.stdout:
            self.logger.debug('{}: {}'.format(self.vm['name'], line))

        self.proc.wait()

        self.logger.info('Destroying {}'.format(self.vm['name']))

        Popen(['bhyvectl', '--destroy', '--vm={}'.format(self.vm['name'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE).wait()

        while self.taps:
            netif.destroy_interface(self.taps.pop())

        self.manager._vm.pop(self.vm['id'], None)

    def stop(self):
        if self.proc:
            try:
                os.kill(self.proc.pid, 15)
            except ProcessLookupError as e:
                # Already stopped, process do not exist anymore
                if e.errno != errno.ESRCH:
                    raise
            return True

    def running(self):
        if self.proc:
            try:
                os.kill(self.proc.pid, 0)
            except OSError:
                return False
            return True
        return False


class VMUtils(object):

    def is_container(data):
        if data.get('vm_type') == 'Container Provider':
            return True
        else:
            return False

    def create_images_path(data):
        images_path = data.get('container_path') + '/.container_images/'
        dir_path = os.path.dirname(images_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        return dir_path


class VMService(CRUDService):

    class Config:
        namespace = 'vm'

    def __init__(self, *args, **kwargs):
        super(VMService, self).__init__(*args, **kwargs)
        self._manager = VMManager(self)
        self.vmutils = VMUtils


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

    @accepts(Ref('query-filters'), Ref('query-options'))
    def query(self, filters=None, options=None):
        options = options or {}
        options['extend'] = 'vm._extend_vm'
        return self.middleware.call('datastore.query', 'vm.vm', filters, options)

    def _extend_vm(self, vm):
        vm['devices'] = []
        for device in self.middleware.call('datastore.query', 'vm.device', [('vm__id', '=', vm['id'])]):
            device.pop('id', None)
            device.pop('vm', None)
            vm['devices'].append(device)
        return vm

    @accepts(Dict(
        'data',
        Str('name'),
        Str('description'),
        Int('vcpus'),
        Int('memory'),
        Str('bootloader'),
        List("devices"),
        Str('vm_type'),
        Str('container_type'),
        Str('container_path'),
        ))
    def do_create(self, data):
        """Create a VM."""
        devices = data.pop('devices')

        pk = self.middleware.call('datastore.insert', 'vm.vm', data)

        if self.vmutils.is_container(data) is True:
            logger.debug("===> Creating directories")
            image_url = CONTAINER_IMAGES.get('coreos')
            image_path = self.vmutils.create_images_path(data) + '/' + image_url.split('/')[-1]

            with Client() as c:
                try:
                    c.call('vm.fetch_image', image_url, image_path)
                except CallTimeout:
                    logger.debug("===> Problem to connect with the middlewared.")
                    raise

            logger.debug("===> Fetching image: %s" % (image_path))

        for device in devices:
            device['vm'] = pk
            self.middleware.call('datastore.insert', 'vm.device', device)
        return pk

    @accepts(Int('id'), Dict(
        'data',
        Str('name'),
        Str('description'),
        Int('vcpus'),
        Int('memory'),
        Str('bootloader'),
        Str('vm_type'),
        Str('container_type'),
        ))
    def do_update(self, id, data):
        """Update all information of a specific VM."""
        return self.middleware.call('datastore.update', 'vm.vm', id, data)

    @accepts(Int('id'))
    def do_delete(self, id):
        """Delete a VM."""
        return self.middleware.call('datastore.delete', 'vm.vm', id)

    @accepts(Int('id'))
    def start(self, id):
        """Start a VM."""
        return self._manager.start(id)

    @accepts(Int('id'))
    def stop(self, id):
        """Stop a VM."""
        return self._manager.stop(id)

    @accepts(Int('id'))
    def status(self, id):
        """Get the status of a VM, if it is RUNNING or STOPPED."""
        return self._manager.status(id)

    def fetch_hookreport(self, blocknum, blocksize, totalsize, job):
        """Hook to report the download progress."""
        readchunk = blocknum * blocksize
        if totalsize > 0:
            percent = readchunk * 1e2 / totalsize
            job.set_progress(int(percent), 'Downloading', {'downloaded': readchunk, 'total': totalsize})

    @accepts(Str('url'), Str('file_name'))
    @job(lock='container')
    def fetch_image(self, job, url, file_name):
        """Fetch an image from a given URL and save to a file."""
        if os.path.exists(file_name) is False:
            logger.debug("===> Downloading: %s" % (url))
            urlretrieve(url, file_name,
                        lambda nb, bs, fs, job=job: self.fetch_hookreport(nb, bs, fs, job))


def kmod_load():
    kldstat = Popen(['/sbin/kldstat'], stdout=subprocess.PIPE).communicate()[0]
    if 'vmm.ko' not in kldstat:
        Popen(['/sbin/kldload', 'vmm'])
    if 'nmdm.ko' not in kldstat:
        Popen(['/sbin/kldload', 'nmdm'])

def setup(middleware):
    gevent.spawn(kmod_load)
