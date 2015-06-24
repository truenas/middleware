#+
# Copyright 2015 iXsystems, Inc.
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


import os
import errno
import uuid
import logging
import libzfs
import nvpair
from dispatcher.rpc import RpcException, accepts, returns, description, private
from dispatcher.rpc import SchemaHelper as h
from task import Task, Provider

SYSTEM_DIR = '/var/db/system'
logger = logging.getLogger('SystemDataset')


def create_system_dataset(dispatcher, pool):
    logger.warning('Creating system dataset on pool {0}'.format(pool))
    zfs = libzfs.ZFS()
    dsid = dispatcher.configstore.get('system.dataset.id')
    pool = zfs.get(pool)
    try:
        zfs.get_dataset('{0}/.system-{1}'.format(pool.name, dsid))
        return
    except libzfs.ZFSException:
        nv = nvpair.NVList()
        nv['mountpoint'] = 'none'
        pool.create('{0}/.system-{1}'.format(pool.name, dsid), nv)


def remove_system_dataset(dispatcher, pool):
    logger.warning('Removing system dataset from pool {0}'.format(pool))
    zfs = libzfs.ZFS()
    dsid = dispatcher.configstore.get('system.dataset.id')
    pool = zfs.get(pool)
    try:
        ds = zfs.get_dataset('{0}/.system-{1}'.format(pool.name, dsid))
        ds.umount()
        ds.delete()
    except libzfs.ZFSException:
        pass


def mount_system_dataset(dispatcher, pool, path):
    logger.warning('Mounting system dataset from pool {0} on {1}'.format(pool, path))
    zfs = libzfs.ZFS()
    dsid = dispatcher.configstore.get('system.dataset.id')
    pool = zfs.get(pool)
    try:
        ds = zfs.get_dataset('{0}/.system-{1}'.format(pool.name, dsid))
        if ds.mountpoint == path:
            return

        ds.properties['mountpoint'].value = path
        ds.mount()
        return
    except libzfs.ZFSException:
        raise


def umount_system_dataset(dispatcher, pool):
    zfs = libzfs.ZFS()
    dsid = dispatcher.configstore.get('system.dataset.id')
    pool = zfs.get(pool)
    try:
        ds = zfs.get_dataset('{0}/.system-{1}'.format(pool, dsid))
        ds.properties['mountpoint'].value = 'none'
        ds.umount()
        return
    except libzfs.ZFSException:
        pass


def move_system_dataset(dispatcher, src_pool, dst_pool):
    logger.warning('Migrating system dataset from pool {0} to {1}'.format(src_pool, dst_pool))
    zfs = libzfs.ZFS()
    dsid = dispatcher.configstore.get('system.dataset.id')
    tmpath = os.tempnam('/tmp')
    src_ds = zfs.get_dataset('{0}/.system-{1}'.format(src_pool, dsid))
    create_system_dataset(dispatcher, dst_pool)
    mount_system_dataset(dispatcher, dst_pool, tmpath)

    dst_ds = zfs.get_dataset('{0}/.system-{1}'.format(dst_pool, dsid))
    pipe = os.pipe()
    src_ds.send(pipe[0])
    dst_ds.receive(pipe[1], force=True)
    os.close(pipe[0])
    os.close(pipe[1])

    umount_system_dataset(dispatcher, src_pool)
    mount_system_dataset(dispatcher, dst_pool, SYSTEM_DIR)
    remove_system_dataset(dispatcher, src_pool)


class SystemDatasetProvider(Provider):
    @private
    @description("Initializes the .system dataset")
    @accepts()
    @returns()
    def init(self):
        pool = self.configstore.get('system.dataset.pool')
        create_system_dataset(self.dispatcher, pool)
        mount_system_dataset(self.dispatcher, pool, SYSTEM_DIR)

    @private
    @description("Creates directory in .system dataset and returns reference to it")
    @accepts(str)
    @returns(str)
    def request_directory(self, name):
        path = os.path.join(SYSTEM_DIR, name)
        if os.path.exists(path):
            if os.path.isdir(path):
                return path

            raise RpcException(errno.EPERM, 'Cannot grant directory {0}'.format(name))

        os.mkdir(path)
        return path

    @description("Returns current .system dataset parameters")
    @returns(h.object())
    def status(self):
        return {
            'id': self.configstore.get('system.dataset.id'),
            'pool': self.configstore.get('system.dataset.pool')
        }


@description("Updates .system dataset configuration")
@accepts(str)
class SystemDatasetConfigure(Task):
    def verify(self, pool):
        return ['service:syslog', 'service:statd']

    def run(self, pool):
        pass


def _depends():
    return ['ZfsPlugin', 'VolumePlugin']


def _init(dispatcher, plugin):
    def on_volumes_changed(args):
        if args['operation'] == 'create':
            pass

    def volume_pre_destroy(args):
        # Evacuate .system dataset from the pool
        if dispatcher.configstore.get('system.dataset.pool') == args['name']:
            pass

    if not dispatcher.configstore.get('system.dataset.id'):
        dsid = uuid.uuid4().hex[:8]
        dispatcher.configstore.set('system.dataset.id', dsid)
        logger.info('New system dataset ID: {0}'.format(dsid))

    plugin.register_event_handler('volumes.changed', on_volumes_changed)
    plugin.attach_hook('volumes.pre-destroy', volume_pre_destroy)
    plugin.attach_hook('volumes.pre-detach', volume_pre_destroy)
    plugin.register_provider('system-dataset', SystemDatasetProvider)
    plugin.register_task_handler('system-dataset.configure', SystemDatasetConfigure)

    plugin.register_hook('system-dataset.pre-detach')
    plugin.register_hook('system-dataset.pre-attach')

    dispatcher.call_sync('system-dataset.init')
