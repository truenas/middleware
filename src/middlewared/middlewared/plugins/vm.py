from middlewared.service import CRUDService
from middlewared.utils import Popen

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
            '-c', str(vm['vcpus']),
            '-m', str(vm['memory']),
            '-l', 'com1,stdio',
        ]

        if vm['bootloader'] == 'UEFI':
            args.extend([
                '-l', 'bootrom,/usr/local/share/uefi-firmware/BHYVE_UEFI.fd'
            ])
            idx = 3
        else:
            args.extend(['-s', '0:0,hostbridge'])
            idx = 1

        proc = Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in proc.stdout:
            self.service.logger.debug('{}: {}', self.vm['name'], line)

        proc.wait()


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
        vm = self.query(('id', '=', id), {'get': True})

        supervisor = self.__vm[id] = VMSupervisor(self, vm)

        return True
