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
from gevent.event import Event
from query import filter_query
from lib import zfs
from lib.system import system, SubprocessException
from task import Provider, Task, TaskStatus, TaskException, VerifyException
from dispatcher.rpc import accepts, returns, description
from balancer import TaskState
from cache import CacheStore


zpool_cache = CacheStore()


@description("Provides information about ZFS pools")
class ZpoolProvider(Provider):
    @description("Lists ZFS pools")
    @returns({
        'type': 'array',
        'items': {
            'type': {'$ref': '#/definitions/pool'}
        }
    })
    def query(self, filter=None, params=None):
        return filter_query(
            zpool_cache.validvalues(),
            *(filter or []),
            **(params or {})
        )

    @description("Gets ZFS pool status")
    @returns({
        '$ref': '#/definitions/pool'
    })
    def pool_status(self, pool):
        return str(zfs.zpool_status(pool))

    def get_capabilities(self):
        return {
            'vdev-types': {
                'disk': {
                    'min-devices': 1,
                    'max-devices': 1
                },
                'mirror': {
                    'min-devices': 2
                },
                'raidz1': {
                    'min-devices': 2
                },
                'raidz2': {
                    'min-devices': 3
                },
                'raidz3': {
                    'min-devices': 4
                },
                'spare': {
                    'min-devices': 1
                }
            },
            'vdev-groups': {
                'data': {
                    'allowed-vdevs': ['disk', 'file', 'mirror', 'raidz1', 'raidz2', 'raidz3', 'spare']
                },
                'log': {
                    'allowed-vdevs': ['disk', 'mirror']
                },
                'cache': {
                    'allowed-vdevs': ['disk']
                }
            }
        }


class ZfsProvider(Provider):
    def list_datasets(self, pool):
        zfs.list_datasets(pool, recursive=True, include_root=True)

    def list_snapshots(self, pool):
        return []


@description("Scrubs ZFS pool")
@accepts({
    'title': 'pool',
    'type': 'string'
})
class ZpoolScrubTask(Task):
    def __init__(self, dispatcher):
        super(ZpoolScrubTask, self).__init__(dispatcher)
        self.pool = None
        self.started = False
        self.finish_event = Event()

    def __scrub_finished(self, args):
        self.state = TaskState.FINISHED
        if args["pool"] == self.pool:
            self.finish_event.set()

    def describe(self, pool):
        return "Scrubbing pool {0}".format(pool)

    def run(self, pool):
        self.pool = pool
        self.dispatcher.register_event_handler("fs.zfs.scrub.finish", self.__scrub_finished)
        self.finish_event.clear()
        try:
            system("/sbin/zpool", "scrub", self.pool)
            self.started = True
        except SubprocessException, e:
            raise TaskException(errno.EINVAL, e.err)

        self.finish_event.wait()
        return self.state

    def abort(self):
        try:
            system("/sbin/zpool", "scrub", "-s", self.pool)
        except SubprocessException, e:
            raise TaskException(errno.EINVAL, e.err)

        self.state = TaskState.ABORTED
        self.finish_event.set()
        return True

    def get_status(self):
        if not self.started:
            return TaskStatus(0, "Waiting to start...")

        scrub = zfs.zpool_status(self.pool).scrub

        if scrub["status"] == "IN_PROGRESS":
            self.progress = float(scrub["progress"])
            return TaskStatus(self.progress, "In progress...")

        if scrub["status"] == "CANCELED":
            self.state = TaskState.ABORTED
            self.finish_event.set()
            return TaskStatus(self.progress, "Canceled")

        if scrub["status"] == "CANCELED":
            self.finish_event.set()
            return TaskStatus(100, "Finished")

    def verify(self, pool):
        pool = zfs.zpool_status(pool)
        return pool.get_disks()


class ZpoolCreateTask(Task):
    def __partition_to_disk(self, part):
        result = self.dispatcher.rpc.call_sync('disk.get_partition_config', part)
        return result['disk']

    def __get_disks(self, topology):
        result = []
        for gname, g in topology['groups'].items():
            for t in g['vdevs']:
                result += [self.__partition_to_disk(i) for i in t['disks']]

        return result

    def __get_vdevs(self, topology):
        result = []
        for name, grp in topology['groups'].items():
            if name in ('cache', 'log', 'spare'):
                result.append(name)

            for i in filter(lambda x: x['type'] == 'stripe', grp['vdevs']):
                result += i['disks']

            for i in filter(lambda x: x['type'] != 'stripe', grp['vdevs']):
                result.append(i['type'])
                result += i['disks']

        return result

    def verify(self, name, topology, params=None):
        if name in zfs.list_pools():
            raise VerifyException(errno.EEXIST, 'Pool with same name already exists')

        return self.__get_disks(topology)

    def run(self, name, topology, params=None):
        mountpoint = params.get('mountpoint', '/{0}'.format(name))
        altroot = params.get('altroot', '/volumes')
        system(
            'zpool', 'create',
            '-o', 'cachefile=/data/zfs/zpool.cache',
            '-o', 'failmode=continue',
            '-o', 'autoexpand=on',
            '-o', 'altroot=' + altroot,
            '-O', 'compression=lz4',
            '-O', 'aclmode=passthrough',
            '-O', 'aclinherit=passthrough',
            '-f', '-m', mountpoint,
            name, *self.__get_vdevs(topology)
        )

        generate_zpool_cache()


class ZpoolConfigureTask(Task):
    def verify(self, pool, updated_props):
        if not zpool_cache.exists(pool):
            raise VerifyException(errno.ENOENT, "Pool {0} not found".format(pool))

        return get_pool_disks(pool)

    def run(self, pool, updated_props):
        for prop, value in updated_props:
            zfs.zpool_set(pool, prop, value)

        generate_zpool_cache()


class ZpoolDestroyTask(Task):
    def verify(self, pool):
        pass

    def run(self, pool):
        pass


class ZpoolExtendTask(Task):
    def verify(self, pool, new_vdevs, updated_vdevs):
        pass

    def run(self, pool, new_vdevs, updated_vdevs):
        pass


class ZpoolImportTask(Task):
    pass


class ZpoolExportTask(Task):
    pass


class ZfsDatasetCreateTask(Task):
    def verify(self, pool, path, params=None):
        pool = zpool_cache.get(pool)
        if path in pool['datasets']:
            raise VerifyException(errno.EEXIST, "Dataset {0} on pool {1} already exists".format(pool, path))

        return

    def run(self, pool, path, params=None):
        system('/sbin/zfs', 'create', '{0}/{1}'.format(pool, path))


class ZfsVolumeCreateTask(Task):
    def verify(self, pool, path, size, params=None):
        pool = zpool_cache.get(pool)
        if path in pool['datasets']:
            raise VerifyException(errno.EEXIST, "Dataset {0} on pool {1} already exists".format(pool, path))

        return

    def run(self, pool, path, size, params=None):
        system('/sbin/zfs', 'create', '{0}/{1}'.format(pool, path))
        generate_zpool_cache()


class ZfsConfigureTask(Task):
    def verify(self, pool, path, params=None):
        pool = zpool_cache.get(pool)
        if path in pool['datasets']:
            raise VerifyException(errno.EEXIST, "Dataset {0} on pool {1} already exists".format(pool, path))

        return

    def run(self, pool, path, params=None):
        system('/sbin/zfs', 'create', '{0}/{1}'.format(pool, path))
        generate_zpool_cache()


class ZfsDestroyTask(Task):
    def verify(self, pool, path, params=None):
        pool = zpool_cache.get(pool)
        if path in pool['datasets']:
            raise VerifyException(errno.EEXIST, "Dataset {0} on pool {1} already exists".format(pool, path))

        return

    def run(self, pool, path, params=None):
        system('/sbin/zfs', 'create', '{0}/{1}'.format(pool, path))
        generate_zpool_cache()


def get_pool_disks(pool):
    pass


def generate_zpool_cache():
    for pname in zfs.list_pools():
        zpool_cache.put(pname, {
            'pool': zfs.zpool_status(pname),
            'datasets': zfs.list_datasets(pname, recursive=True, include_root=True)
        })


def _depends():
    return ['DevdPlugin', 'DiskPlugin']


def _init(dispatcher):
    def on_zfs_config_sync(args):
        generate_zpool_cache()

    dispatcher.register_event_handler('fs.zfs.config_sync', on_zfs_config_sync)
    dispatcher.register_provider('zfs.pool', ZpoolProvider)
    dispatcher.register_task_handler('zfs.pool.create', ZpoolCreateTask)
    dispatcher.register_task_handler('zfs.pool.configure', ZpoolConfigureTask)
    dispatcher.register_task_handler('zfs.pool.extend', ZpoolExtendTask)
    dispatcher.register_task_handler('zfs.pool.import', ZpoolImportTask)
    dispatcher.register_task_handler('zfs.pool.export', ZpoolExportTask)
    dispatcher.register_task_handler('zfs.pool.destroy', ZpoolDestroyTask)
    dispatcher.register_task_handler('zfs.pool.scrub', ZpoolScrubTask)

    dispatcher.register_task_handler('zfs.create_dataset', ZfsDatasetCreateTask)
    dispatcher.register_task_handler('zfs.create_zvol', ZfsVolumeCreateTask)
    dispatcher.register_task_handler('zfs.configure', ZfsConfigureTask)
    dispatcher.register_task_handler('zfs.destroy', ZfsDestroyTask)

    generate_zpool_cache()