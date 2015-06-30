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
from gevent.lock import RLock
from task import Provider, Task, ProgressTask, TaskException, VerifyException, query
from dispatcher.rpc import RpcException, description, accepts, returns
from dispatcher.rpc import SchemaHelper as h
from utils import first_or_default
from datastore import DuplicateKeyException


VOLUMES_ROOT = '/volumes'
volumes_lock = RLock()


def flatten_datasets(root):
    for ds in root['children']:
        for c in flatten_datasets(ds):
            yield c

    del root['children']
    yield root


@description("Provides access to volumes information")
class VolumeProvider(Provider):
    @query('volume')
    def query(self, filter=None, params=None):
        def extend(vol):
            config = self.get_config(vol['name'])
            if not config:
                vol['status'] = 'UNKNOWN'
            else:
                topology = config['groups']
                for vdev, _ in iterate_vdevs(topology):
                    vdev['path'] = self.dispatcher.call_sync('disks.partition_to_disk', vdev['path'])

                vol['topology'] = topology
                vol['status'] = config['status']
                vol['scan'] = config['scan']
                vol['properties'] = config['properties']
                vol['datasets'] = list(flatten_datasets(config['root_dataset']))

            return vol

        return self.datastore.query('volumes', *(filter or []), callback=extend, **(params or {}))

    @description("Finds volumes available for import")
    @returns(h.array(
        h.object(properties={
            'id': str,
            'name': str,
            'topology': h.ref('volume-topology'),
            'status': str
        })
    ))
    def find(self):
        result = []
        for pool in self.dispatcher.call_sync('zfs.pool.find'):
            topology = pool['groups']
            for vdev, _ in iterate_vdevs(topology):
                try:
                    vdev['path'] = self.dispatcher.call_sync('disks.partition_to_disk', vdev['path'])
                except RpcException:
                    pass

            result.append({
                'id': str(pool['guid']),
                'name': pool['name'],
                'topology': topology,
                'status': pool['status']
            })

        return result

    @accepts(str)
    @returns(str)
    def resolve_path(self, path):
        volname, _, rest = path.partition(':')
        volume = self.query([('name', '=', volname)], {'single': True})
        if not volume:
            raise RpcException(errno.ENOENT, 'Volume {0} not found'.format(volname))

        return os.path.join(volume['mountpoint'], rest)

    @description("Extracts volume name, dataset name and relative path from full path")
    @accepts(str)
    @returns(h.tuple(str, str, str))
    def decode_path(self, path):
        path = os.path.normpath(path)[1:]
        tokens = path.split(os.sep)

        if tokens[0] != 'volumes':
            raise RpcException(errno.EINVAL, 'Invalid path')

        volname = tokens[1]
        config = self.get_config(volname)
        datasets = map(lambda d: d['name'], flatten_datasets(config['root_dataset']))
        n = len(tokens)

        while n > 0:
            fragment = '/'.join(tokens[1:n])
            if fragment in datasets:
                return volname, fragment, '/'.join(tokens[n:])

            n -= 1

        raise RpcException(errno.ENOENT, 'Cannot look up path')

    @accepts(str)
    @returns(h.array(str))
    def get_volume_disks(self, name):
        result = []
        for dev in self.dispatcher.call_sync('zfs.pool.get_disks', name):
            result.append(self.dispatcher.call_sync('disks.partition_to_disk', dev))

        return result

    @returns(h.array(str))
    def get_available_disks(self):
        disks = set([d['path'] for d in self.dispatcher.call_sync('disks.query')])
        for pool in self.dispatcher.call_sync('zfs.pool.query'):
            for dev in self.dispatcher.call_sync('zfs.pool.get_disks', pool['name']):
                disk = self.dispatcher.call_sync('disks.partition_to_disk', dev)
                disks.remove(disk)

        return list(disks)

    def get_disk_disposition(self, disk):
        pass

    @accepts(str)
    def get_config(self, volume):
        return self.dispatcher.call_sync('zfs.pool.query', [('name', '=', volume)], {'single': True})

    @accepts(str)
    def get_capabilities(self, type):
        if type == 'zfs':
            return self.dispatcher.call_sync('zfs.pool.get_capabilities')

        raise RpcException(errno.EINVAL, 'Invalid volume type')


@description("Creates new volume")
@accepts(h.ref('volume'))
class VolumeCreateTask(ProgressTask):
    def verify(self, volume):
        if self.datastore.exists('volumes', ('name', '=', volume['name'])):
            raise VerifyException(errno.EEXIST, 'Volume with same name already exists')

        return ['disk:{0}'.format(i) for i, _ in get_disks(volume['topology'])]

    def run(self, volume):
        subtasks = []
        name = volume['name']
        type = volume['type']
        params = volume.get('params') or {}
        mountpoint = params.pop('mountpoint', os.path.join(VOLUMES_ROOT, volume['name']))

        if type != 'zfs':
            raise TaskException(errno.EINVAL, 'Invalid volume type')

        for dname, dgroup in get_disks(volume['topology']):
            subtasks.append(self.run_subtask('disk.format.gpt', dname, 'freebsd-zfs', {
                'blocksize': params.get('blocksize', 4096),
                'swapsize': params.get('swapsize', 2048) if dgroup == 'data' else 0
            }))

        self.set_progress(10)
        self.join_subtasks(*subtasks)
        self.set_progress(40)

        with volumes_lock:
            self.join_subtasks(self.run_subtask('zfs.pool.create', name, convert_topology_to_gptids(self.dispatcher, volume['topology'])))
            self.set_progress(60)
            self.join_subtasks(self.run_subtask('zfs.mount', name))
            self.set_progress(80)

            pool = self.dispatcher.call_sync('zfs.pool.query', [('name', '=', name)]).pop()
            id = self.datastore.insert('volumes', {
                'id': str(pool['guid']),
                'name': name,
                'type': type,
                'mountpoint': mountpoint
            })

        self.set_progress(90)
        self.dispatcher.dispatch_event('volumes.changed', {
            'operation': 'create',
            'ids': [id]
        })


@description("Creates new volume and automatically guesses disks layout")
@accepts(str, str, h.array(str), h.object())
class VolumeAutoCreateTask(Task):
    def verify(self, name, type, disks, params=None):
        if self.datastore.exists('volumes', ('name', '=', name)):
            raise VerifyException(errno.EEXIST, 'Volume with same name already exists')

        return ['disk:{0}'.format(os.path.join('/dev', i)) for i in disks]

    def run(self, name, type, disks, params=None):
        vdevs = []
        if len(disks) % 3 == 0:
            for i in xrange(0, len(disks), 3):
                vdevs.append({
                    'type': 'raidz1',
                    'children': [{'type': 'disk', 'path': os.path.join('/dev', i)} for i in disks[i:i+3]]
                })
        elif len(disks) % 2 == 0:
            for i in xrange(0, len(disks), 2):
                vdevs.append({
                    'type': 'mirror',
                    'children': [{'type': 'disk', 'path': os.path.join('/dev', i)} for i in disks[i:i+2]]
                })
        else:
            vdevs = [{'type': 'disk', 'path': os.path.join('/dev', i)} for i in disks]

        self.join_subtasks(self.run_subtask('volume.create', {
            'name': name,
            'type': type,
            'topology': {'data': vdevs},
            'params': params
        }))


@description("Destroys active volume")
@accepts(str)
class VolumeDestroyTask(Task):
    def verify(self, name):
        if not self.datastore.exists('volumes', ('name', '=', name)):
            raise VerifyException(errno.ENOENT, 'Volume {0} not found'.format(id))

        try:
            disks = self.dispatcher.call_sync('volumes.get_volume_disks', name)
            return ['disk:{0}'.format(d) for d in disks]
        except RpcException, e:
            return []

    def run(self, name):
        vol = self.datastore.get_one('volumes', ('name', '=', name))
        config = self.dispatcher.call_sync('volumes.get_config', name)

        self.dispatcher.run_hook('volumes.pre-destroy', {'name': name})

        if config:
            self.join_subtasks(self.run_subtask('zfs.umount', name))
            self.join_subtasks(self.run_subtask('zfs.pool.destroy', name))

        self.datastore.delete('volumes', vol['id'])

        self.dispatcher.dispatch_event('volumes.changed', {
            'operation': 'delete',
            'ids': [vol['id']]
        })


@description("Updates configuration of existing volume")
@accepts(str, h.ref('volume'))
class VolumeUpdateTask(Task):
    def verify(self, name, updated_params):
        topology = updated_params.get('topology')
        return ['disk:{0}'.format(i) for i, _ in get_disks(self.dispatcher, topology)]

    def run(self, name, updated_params):
        if 'topology' in updated_params:
            new_vdevs = {}
            updated_vdevs = {}
            params = {}
            subtasks = []

            for group, vdevs in updated_params['topology'].items():
                for vdev in vdevs:
                    if 'guid' not in vdev:
                        new_vdevs.setdefault(group, []).append(vdev)
                        continue

                # look for vdev in existing configuration using guid
                pass

            for vdev, group in iterate_vdevs(new_vdevs):
                if vdev['type'] == 'disk':
                    subtasks.append(self.run_subtask('disk.format.gpt', vdev['path'], 'freebsd-zfs', {
                        'blocksize': params.get('blocksize', 4096),
                        'swapsize': params.get('swapsize', 2048) if group == 'data' else 0
                    }))

            self.join_subtasks(*subtasks)

            new_vdevs = convert_topology_to_gptids(self.dispatcher, new_vdevs)
            self.join_subtasks(self.run_subtask('zfs.pool.extend', name, new_vdevs, updated_vdevs))


@description("Imports previously exported volume")
@accepts(str, str, h.object())
class VolumeImportTask(Task):
    def verify(self, id, new_name, params=None):
        if self.datastore.exists('volumes', ('id', '=', id)):
            raise VerifyException(errno.ENOENT, 'Volume with id {0} already exists'.format(id))

        if self.datastore.exists('volumes', ('name', '=', new_name)):
            raise VerifyException(errno.ENOENT, 'Volume with name {0} already exists'.format(new_name))

        return self.verify_subtask('zfs.pool.import', id)

    def run(self, id, new_name, params=None):
        mountpoint = os.path.join(VOLUMES_ROOT, new_name)
        self.join_subtasks(self.run_subtask('zfs.pool.import', id, new_name, params))
        self.join_subtasks(self.run_subtask('zfs.configure', new_name, {'mountpoint': mountpoint}))
        self.join_subtasks(self.run_subtask('zfs.mount', new_name))

        new_id = self.datastore.insert('volumes', {
            'id': id,
            'name': new_name,
            'type': 'zfs',
            'mountpoint': mountpoint
        })

        self.dispatcher.dispatch_event('volumes.changed', {
            'operation': 'create',
            'ids': [new_id]
        })


@description("Exports active volume")
@accepts(str)
class VolumeDetachTask(Task):
    def verify(self, name):
        if not self.datastore.exists('volumes', ('name', '=', name)):
            raise VerifyException(errno.ENOENT, 'Volume {0} not found'.format(name))

        return ['disk:{0}'.format(d) for d in self.dispatcher.call_sync('volumes.get_volume_disks', name)]

    def run(self, name):
        vol = self.datastore.get_one('volumes', ('name', '=', name))
        self.join_subtasks(self.run_subtask('zfs.umount', name))
        self.join_subtasks(self.run_subtask('zfs.pool.export', name))
        self.datastore.delete('volumes', vol['id'])

        self.dispatcher.dispatch_event('volumes.changed', {
            'operation': 'delete',
            'ids': [vol['id']]
        })


class DatasetCreateTask(Task):
    def verify(self, pool_name, path, params=None):
        if not self.datastore.exists('volumes', ('name', '=', pool_name)):
            raise VerifyException(errno.ENOENT, 'Volume {0} not found'.format(pool_name))

        return ['zpool:{0}'.format(pool_name)]

    def run(self, pool_name, path, params=None):
        self.join_subtasks(self.run_subtask('zfs.create_dataset', pool_name, path, params))
        self.join_subtasks(self.run_subtask('zfs.mount', path))


class DatasetDeleteTask(Task):
    def verify(self, pool_name, path):
        if not self.datastore.exists('volumes', ('name', '=', pool_name)):
            raise VerifyException(errno.ENOENT, 'Volume {0} not found'.format(pool_name))

        return ['zpool:{0}'.format(pool_name)]

    def run(self, pool_name, path):
        self.join_subtasks(self.run_subtask('zfs.umount', path))
        self.join_subtasks(self.run_subtask('zfs.destroy', pool_name, path))


class DatasetConfigureTask(Task):
    def verify(self, pool_name, path, updated_params):
        if not self.datastore.exists('volumes', ('name', '=', pool_name)):
            raise VerifyException(errno.ENOENT, 'Volume {0} not found'.format(pool_name))

        return ['zpool:{0}'.format(pool_name)]

    def run(self, pool_name, path, updated_params):
        pass


def iterate_vdevs(topology):
    for name, grp in topology.items():
        for vdev in grp:
            if vdev['type'] == 'disk':
                yield vdev, name
                continue

            if 'children' in vdev:
                for child in vdev['children']:
                    yield child, name


def get_disks(topology):
    for vdev, gname in iterate_vdevs(topology):
        yield vdev['path'], gname


def get_disk_gptid(dispatcher, disk):
    config = dispatcher.call_sync('disks.get_disk_config', disk)
    return config.get('data-partition-path', disk)


def convert_topology_to_gptids(dispatcher, topology):
    topology = topology.copy()
    for vdev, _ in iterate_vdevs(topology):
        vdev['path'] = get_disk_gptid(dispatcher, vdev['path'])

    return topology


def _depends():
    return ['DevdPlugin', 'ZfsPlugin']


def _init(dispatcher, plugin):
    boot_pool = dispatcher.call_sync('zfs.pool.get_boot_pool')

    def on_pool_change(args):
        ids = filter(lambda i: i != boot_pool['guid'], args['ids'])

        if args['operation'] == 'delete':
            for i in args['ids']:
                dispatcher.datastore.delete('volumes', i)

        if args['operation'] == 'create':
            for i in args['ids']:
                pool = dispatcher.call_sync('zfs.pool.query', [('guid', '=', i)], {'single': True})
                with volumes_lock:
                    try:
                        dispatcher.datastore.insert('volumes', {
                            'id': i,
                            'name': pool['name'],
                            'type': 'zfs'
                        })
                    except DuplicateKeyException:
                        # already inserted by task
                        pass

        dispatcher.dispatch_event('volumes.changed', {
            'operation': args['operation'],
            'ids': ids
        })

    plugin.register_schema_definition('volume', {
        'type': 'object',
        'title': 'volume',
        'properties': {
            'id': {'type': 'string'},
            'name': {'type': 'string'},
            'type': {
                'type': 'string',
                'enum': ['zfs']
            },
            'topology': {'$ref': 'zfs-topology'},
            'params': {'type': 'object'}
        }
    })

    dispatcher.require_collection('volumes')
    plugin.register_provider('volumes', VolumeProvider)
    plugin.register_task_handler('volume.create', VolumeCreateTask)
    plugin.register_task_handler('volume.create_auto', VolumeAutoCreateTask)
    plugin.register_task_handler('volume.destroy', VolumeDestroyTask)
    plugin.register_task_handler('volume.import', VolumeImportTask)
    plugin.register_task_handler('volume.detach', VolumeDetachTask)
    plugin.register_task_handler('volume.update', VolumeUpdateTask)
    plugin.register_task_handler('volume.dataset.create', DatasetCreateTask)
    plugin.register_task_handler('volume.dataset.delete', DatasetDeleteTask)
    plugin.register_task_handler('volume.dataset.update', DatasetConfigureTask)

    plugin.register_hook('volumes.pre-destroy')
    plugin.register_hook('volumes.pre-detach')
    plugin.register_hook('volumes.pre-create')
    plugin.register_hook('volumes.pre-attach')

    plugin.register_event_handler('zfs.pool.changed', on_pool_change)
    plugin.register_event_type('volumes.changed')

    for vol in dispatcher.datastore.query('volumes'):
        dispatcher.call_task_sync('zfs.mount', vol['name'], True)
