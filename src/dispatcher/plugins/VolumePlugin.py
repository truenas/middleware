#+
# Copyright 2014 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

import errno
import os
from task import Provider, Task, TaskException, VerifyException, query
from lib.system import system
from lib import zfs
from dispatcher.rpc import RpcException, description, accepts, returns


@description("Provides access to volumes information")
class VolumeProvider(Provider):
    @query
    def query(self, filter=None, params=None):
        return [v['name'] for v in self.datastore.query('volumes')]

    def resolve_path(self, path):
        pass

    def get_config(self, vol):
        return self.datastore.get_one('volumes', ('name', '=', vol))

    def get_capabilities(self, type):
        if type == 'zfs':
            return self.dispatcher.rpc.call_sync('zfs.pool.get_capabilities')

        raise RpcException(errno.EINVAL, 'Invalid volume type')


@description("Creates new volume")
@accepts({
    'type': 'string',
    'title': 'name'
}, {
    'type': 'string',
    'title': 'type'
}, {
    'type': 'object',
    'title': 'topology',
    'properties': {
        'groups': {'type': 'object'}
    }
})
class VolumeCreateTask(Task):
    def __get_disks(self, topology):
        result = []
        for gname, g in topology['groups'].items():
            for t in g['vdevs']:
                result += [(i, gname) for i in t['disks']]

        return result

    def __get_disk_gptid(self, disk):
        config = self.dispatcher.rpc.call_sync('disk.get_config', disk)
        return config.get('data-partition-path', disk)

    def __convert_topology_to_gptids(self, topology):
        topology = topology.copy()
        for name, grp in topology['groups'].items():
            for vdev in grp['vdevs']:
                vdev['disks'] = [self.__get_disk_gptid(d) for d in vdev['disks']]

        return topology

    def verify(self, name, type, topology, params=None):
        if self.datastore.exists('volumes', ('name', '=', name)):
            raise VerifyException(errno.EEXIST, 'Volume with same name already exists')

        return [os.path.basename(i) for i, _ in self.__get_disks(topology)]

    def run(self, name, type, topology, params=None):
        subtasks = []
        params = params or {}
        mountpoint = params.pop('mountpoint', '/{0}'.format(name))
        altroot = params.pop('altroot', '/volumes')

        for dname, dgroup in self.__get_disks(topology):
            subtasks.append(self.run_subtask('disk.format.gpt', dname, 'freebsd-zfs', {
                'blocksize': params.get('blocksize', 4096),
                'swapsize': params.get('swapsize') if dgroup == 'data' else 0
            }))

        self.join_subtasks(*subtasks)
        self.join_subtasks(self.run_subtask('zfs.pool.create', name, self.__convert_topology_to_gptids(topology)))

        pool = zfs.zpool_status(name)

        self.datastore.insert('volumes', {
            'id': pool.id,
            'name': name,
            'type': type,
            'mountpoint': mountpoint
        })

        self.dispatcher.dispatch_event('volume.created', {
            'name': name,
            'id': pool.id,
            'type': type,
            'mountpoint': os.path.join(altroot, mountpoint)
        })


class VolumeDestroyTask(Task):
    def verify(self, name):
        pass

    def run(self, name):
        pass


class VolumeUpdateTask(Task):
    def verify(self, name, ):
        pass


class VolumeImportTask(Task):
    pass


class VolumeDetachTask(Task):
    pass


class DatasetCreateTask(Task):
    pass


def _depends():
    return ['DevdPlugin']


def _init(dispatcher):
    def on_pool_destroy(args):
        guid = args['guid']
        dispatcher.datastore.delete('volumes', guid)

        dispatcher.dispatch_event('volume.destroyed', {
            'name': args['name'],
            'id': guid,
            'type': 'zfs'
        })

    dispatcher.register_schema_definition('volume-vdev', {
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'type': {
                'type': 'string',
                'enum': ['stripe', 'mirror', 'raidz1', 'raidz2', 'raidz3']
            },
            'disks': {
                'type': 'array',
                'items': {'type': 'string'}
            }
        }
    })

    dispatcher.register_schema_definition('volume-topology', {
        'type': 'object',
        'properties': {
            'data': {'$ref': '#/definitions/volume-vdev'},
            'logs': {'$ref': '#/definitions/volume-vdev'},
            'cache': {'$ref': '#/definitions/volume-vdev'},
            'spare': {'$ref': '#/definitions/volume-vdev'}
        }
    })

    dispatcher.register_schema_definition('volume', {
        'type': 'object',
        'title': 'volume',
        'properties': {
            'name': {'type': 'string'},
            'topology': {'$ref': '#/definitions/volume-topology'},
            'params': {'type': 'object'}
        }
    })

    dispatcher.register_event_handler('fs.zfs.pool.destroy', on_pool_destroy)
    dispatcher.require_collection('volumes')
    dispatcher.register_provider('volumes', VolumeProvider)
    dispatcher.register_task_handler('volume.create', VolumeCreateTask)
    dispatcher.register_task_handler('volume.import', VolumeImportTask)
