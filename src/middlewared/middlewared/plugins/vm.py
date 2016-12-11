from middlewared.service import CRUDService
from middlewared.utils import Popen

import gevent
import subprocess


class VMSupervisor(object):

    def __init__(self, service, vm):
        self.service = service
        self.vm = vm

    def run(self):
        args = [
            'bhyve',
            '-A',
            '-P',
            '-H',
            '-c', str(self.vm['vcpus']),
            '-m', str(self.vm['memory']),
            '-l', 'com1,stdio',
        ]

        if self.vm['bootloader'] == 'UEFI':
            args.extend([
                '-l', 'bootrom,/usr/local/share/uefi-firmware/BHYVE_UEFI.fd'
            ])
            idx = 3
        else:
            args.extend(['-s', '0:0,hostbridge'])
            idx = 1

        args.append(self.vm['name'])

        self.service.logger.debug('Starting bhyve: {}'.format(' '.join(args)))
        proc = Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in proc.stdout:
            self.service.logger.debug('{}: {}'.format(self.vm['name'], line))

        proc.wait()

        Popen(['bhyvectl', '--destroy', '--vm={}'.format(self.vm['name'])], stdout=subprocess.PIPE, stderr=subprocess.PIPE).wait()


class VMService(CRUDService):

    class Config:
        namespace = 'vm'

    def __init__(self, *args, **kwargs):
        super(VMService, self).__init__(*args, **kwargs)
        self.__vm = {}

    def query(self, filters=None, options=None):
        return self.middleware.call('datastore.query', 'vm.vm', filters, options)

    def do_create(self, data):
        return self.middleware.call('datastore.insert', 'vm.vm', data)

    def do_update(self, id, data):
        return self.middleware.call('datastore.update', 'vm.vm', id, data)

    def do_delete(self, id):
        return self.middleware.call('datastore.delete', 'vm.vm', id)

    def start(self, id):
        vm = self.query([('id', '=', id)], {'get': True})

        supervisor = self.__vm[id] = VMSupervisor(self, vm)
        gevent.spawn(supervisor.run)

        return True
