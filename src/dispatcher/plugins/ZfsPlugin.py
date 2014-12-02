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
from lib import zfs
from lib.system import system, SubprocessException
from task import Provider, Task, TaskStatus, TaskException
from dispatcher.rpc import accepts, returns, description
from balancer import TaskState

@description("Provides information about ZFS pools")
class ZpoolProvider(Provider):
    @description("Lists ZFS pools")
    @returns({
        'type': 'array',
        'items': {
            'type': {'$ref': '#/definitions/pool'}
        }
    })
    def list_pools(self):
        return zfs.list_pools()

    @description("Gets ZFS pool status")
    @returns({
        '$ref': '#/definitions/pool'
    })
    def pool_status(self, pool):
        return str(zfs.zpool_status(pool))


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
        self.pool = None
        self.dispatcher = dispatcher
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


def _init(dispatcher):
    dispatcher.register_provider('zfs.pool', ZpoolProvider)
    dispatcher.register_task_handler('zfs.pool.scrub', ZpoolScrubTask)