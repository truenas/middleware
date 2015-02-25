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
from dispatcher.rpc import RpcException
from task import Task, Provider

SYSTEM_DIR = '/var/db/system'
logger = logging.getLogger('SystemDataset')


def create_system_dataset(dispatcher, pool):
    zfs = libzfs.ZFS()
    dsid = dispatcher.configstore.get('system.dataset.id')
    pool = zfs.get(pool)
    try:
        zfs.get_dataset('{0}/.system-{1}'.format(pool, dsid))
        return
    except libzfs.ZFSException:
        nv = nvpair.NVList()
        nv['mountpoint'] = 'legacy'
        pool.create('.system-{0}'.format(dsid), nv)


def remove_system_dataset(pool):
    pass


def mount_system_dataset(dispatcher, pool, path):
    zfs = libzfs.ZFS()
    dsid = dispatcher.configstore.get('system.dataset.id')
    pool = zfs.get(pool)
    try:
        ds = zfs.get_dataset('{0}/.system-{1}'.format(pool, dsid))
        ds.properties['mountpoint'] = path
        ds.mount()
        return
    except libzfs.ZFSException:
        pass


def umount_system_dataset(dispatcher, pool):
    zfs = libzfs.ZFS()
    dsid = dispatcher.configstore.get('system.dataset.id')
    pool = zfs.get(pool)
    try:
        ds = zfs.get_dataset('{0}/.system-{1}'.format(pool, dsid))
        ds.umount()
        return
    except libzfs.ZFSException:
        pass


def move_system_dataset(src, dest):
    pass


class SystemDatasetProvider(Provider):
    def init(self):
        pool = self.configstore.get('system.dataset.pool')
        create_system_dataset(self.dispatcher, pool)
        mount_system_dataset(self.dispatcher, pool, SYSTEM_DIR)

    def request_directory(self, name):
        path = os.path.join(SYSTEM_DIR, name)
        if os.path.exists(path):
            if os.path.isdir(path):
                return path

            raise RpcException(errno.EPERM, 'Cannot grant directory {0}'.format(name))

        os.mkdir(path)
        return path

    def status(self):
        return {
            'id': self.configstore.get('system.dataset.id'),
            'pool': self.configstore.get('system.dataset.pool')
        }


class SystemDatasetConfigure(Task):
    def verify(self, pool):
        return ['service:syslog', 'service:statd']

    def run(self, pool):
        pass


def _depends():
    return ['ZfsPlugin']


def _init(dispatcher):
    def on_volumes_changed(args):
        pass

    if not dispatcher.configstore.get('system.dataset.id'):
        dsid = uuid.uuid4().hex[:8]
        dispatcher.configstore.set('system.dataset.id', dsid)
        logger.info('New system dataset ID: {0}'.format(dsid))

    dispatcher.register_event_handler('volumes.changed', on_volumes_changed)
    dispatcher.register_provider('system-dataset', SystemDatasetProvider)
    dispatcher.register_task_handler('system-dataset.configure', SystemDatasetConfigure)