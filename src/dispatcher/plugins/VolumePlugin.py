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
from task import Provider, Task, ProgressTask, TaskException, VerifyException, query
from lib.system import system
from lib import zfs
from dispatcher.rpc import RpcException, description, accepts, returns


@description("Provides access to volumes information")
class VolumeProvider(Provider):
    @query
    def query(self, filter=None, params=None):
        result = []
        for vol in self.datastore.query('volumes', *(filter or []), **(params or {})):
            config = self.get_config(vol['name'])
            topology = config['groups']
            for vdev, _ in iterate_vdevs(topology):
                vdev['path'] = self.dispatcher.call_sync('disk.partition_to_disk', vdev['path'])

            vol['topology'] = topology
            vol['status'] = config['status']
            vol['datasets'] = config['root_dataset']
            result.append(vol)

        return result

    def resolve_path(self, path):
        pass

    def get_volume_disks(self, name):
        result = []
        for dev in self.dispatcher.call_sync('zfs.pool.get_disks', name):
            result.append(self.dispatcher.call_sync('disk.partition_to_disk', dev))

        return result


    def get_available_disks(self):
        disks = set([d['path'] for d in self.dispatcher.call_sync('disk.query')])
        for pool in self.dispatcher.call_sync('zfs.pool.query'):
            for dev in self.dispatcher.call_sync('zfs.pool.get_disks', pool['name']):
                disk = self.dispatcher.call_sync('disk.partition_to_disk', dev)
                disks.remove(disk)

        return list(disks)

    def get_config(self, volume):
        return self.dispatcher.call_sync('zfs.pool.query', [('name', '=', volume)], {'single': True})[0]

    def get_capabilities(self, type):
        if type == 'zfs':
            return self.dispatcher.call_sync('zfs.pool.get_capabilities')

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
class VolumeCreateTask(ProgressTask):
    def __get_disks(self, topology):
        for vdev, gname in iterate_vdevs(topology):
            yield vdev['path'], gname

    def __get_disk_gptid(self, disk):
        config = self.dispatcher.call_sync('disk.get_disk_config', disk)
        return config.get('data-partition-path', disk)

    def __convert_topology_to_gptids(self, topology):
        topology = topology.copy()
        for vdev, _ in iterate_vdevs(topology):
            vdev['path'] = self.__get_disk_gptid(vdev['path'])

        return topology

    def verify(self, name, type, topology, params=None):
        if self.datastore.exists('volumes', ('name', '=', name)):
            raise VerifyException(errno.EEXIST, 'Volume with same name already exists')

        return ['disk:{0}'.format(i) for i, _ in self.__get_disks(topology)]

    def run(self, name, type, topology, params=None):
        subtasks = []
        params = params or {}
        mountpoint = params.pop('mountpoint', '/volumes/{0}'.format(name))

        for dname, dgroup in self.__get_disks(topology):
            subtasks.append(self.run_subtask('disk.format.gpt', dname, 'freebsd-zfs', {
                'blocksize': params.get('blocksize', 4096),
                'swapsize': params.get('swapsize') if dgroup == 'data' else 0
            }))

        self.set_progress(10)
        self.join_subtasks(*subtasks)
        self.set_progress(40)
        self.join_subtasks(self.run_subtask('zfs.pool.create', name, self.__convert_topology_to_gptids(topology)))
        self.set_progress(60)
        self.join_subtasks(self.run_subtask('zfs.mount', name))
        self.set_progress(80)

        pool = self.dispatcher.call_sync('zfs.pool.query', [('name', '=', name)]).pop()

        self.datastore.insert('volumes', {
            'id': str(pool['guid']),
            'name': name,
            'type': type,
            'mountpoint': mountpoint
        })

        self.set_progress(90)
        self.dispatcher.dispatch_event('volume.created', {
            'name': name,
            'id': str(pool['guid']),
            'type': type,
            'mountpoint': os.path.join(mountpoint)
        })


@description("Creates new volume and automatically guesses disks layout")
@accepts({
    'type': 'string',
    'title': 'name'
}, {
    'type': 'string',
    'title': 'type'
}, {
    'type': 'array',
    'title': 'disks',
    'items': {'type': 'string'}
})
class VolumeAutoCreateTask(VolumeCreateTask):
    def verify(self, name, type, disks, params=None):
        if self.datastore.exists('volumes', ('name', '=', name)):
            raise VerifyException(errno.EEXIST, 'Volume with same name already exists')

        return ['disk:{0}'.format(i) for i in disks]

    def run(self, name, type, disks, params=None):
        vdevs = []
        if len(disks) % 3 == 0:
            for i in xrange(0, len(disks), 3):
                vdevs.append({
                    'type': 'raidz',
                    'children': [{'type': 'disk', 'path': i} for i in disks[i:i+3]]
                })
        elif len(disks) % 2 == 0:
            for i in xrange(0, len(disks), 2):
                vdevs.append({
                    'type': 'mirror',
                    'children': [{'type': 'disk', 'path': i} for i in disks[i:i+2]]
                })
        else:
            vdevs = [{'type': 'disk', 'path': i} for i in disks]

        self.join_subtasks(self.run_subtask('volume.create', name, type, {'data': vdevs}, params))


class VolumeDestroyTask(Task):
    def verify(self, name):
        if not self.datastore.exists('volumes', ('name', '=', name)):
            raise VerifyException(errno.ENOENT, 'Volume {0} not found'.format(name))

        return ['disk:{0}'.format(d) for d in self.dispatcher.call_sync('volumes.get_volume_disks', name)]

    def run(self, name):
        vol = self.datastore.get_one('volumes', ('name', '=', name))
        self.join_subtasks(self.run_subtask('zfs.umount', name))
        self.join_subtasks(self.run_subtask('zfs.pool.destroy', name))
        self.datastore.delete('volumes', vol['id'])


class VolumeUpdateTask(Task):
    def verify(self, name, ):
        pass


class VolumeImportTask(Task):
    pass


class VolumeDetachTask(Task):
    pass


class DatasetCreateTask(Task):
    def verify(self, pool_name, path, params=None):
        if not self.datastore.exists('volumes', ('name', '=', pool_name)):
            raise VerifyException(errno.ENOENT, 'Volume {0} not found'.format(pool_name))

        return ['zpool:{0}'.format(pool_name)]

    def run(self, pool_name, path, params=None):
        self.join_subtasks(self.run_subtask('zfs.create_dataset', pool_name, path, params))


def iterate_vdevs(topology):
    for name, grp in topology.items():
        for vdev in grp:
            if vdev['type'] == 'disk':
                yield vdev, name
                continue

            if 'children' in vdev:
                for child in vdev['children']:
                    yield child, name


def _depends():
    return ['DevdPlugin', 'ZfsPlugin']


def _init(dispatcher):
    def on_pool_destroy(args):
        guid = args['guid']
        dispatcher.datastore.delete('volumes', guid)

        dispatcher.dispatch_event('volume.destroyed', {
            'name': args['pool'],
            'id': guid,
            'type': 'zfs'
        })

    dispatcher.register_schema_definition('volume', {
        'type': 'object',
        'title': 'volume',
        'properties': {
            'name': {'type': 'string'},
            'topology': {'$ref': 'definitions/zfs-topology'},
            'params': {'type': 'object'}
        }
    })

    dispatcher.register_event_handler('fs.zfs.pool.destroy', on_pool_destroy)
    dispatcher.require_collection('volumes')
    dispatcher.register_provider('volumes', VolumeProvider)
    dispatcher.register_task_handler('volume.create', VolumeCreateTask)
    dispatcher.register_task_handler('volume.create_auto', VolumeAutoCreateTask)
    dispatcher.register_task_handler('volume.destroy', VolumeDestroyTask)
    dispatcher.register_task_handler('volume.import', VolumeImportTask)
    dispatcher.register_task_handler('volume.dataset.create', DatasetCreateTask)

