#
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
import logging

from dispatcher.rpc import (
    SchemaHelper as h,
    accepts,
    returns,
)
from task import (
    Provider, Task, query
)

logger = logging.getLogger('AlertVolume')


@accepts(None)
class AlertVolumeStatusTask(Task):

    def describe(self,):
        return 'Volumes status alert'

    def verify(self):
        pass

    def run(self):
        for volume in dispatcher.rpc.call_sync('volumes.query'):

            continue  # FIXME: pool status not implemented
            status = self.dispatcher.call_task_sync(
                'zfs.pool.status', volume['name']
            )
            if status['status'] != 'ONLINE':

                self.dispatcher.call_task_sync('alert.emit', {
                    'name': 'alert.volumes.status',
                    'description': 'The volume {0} state is {1}'.format(
                        volume['name'],
                        status['status'],
                    ),
                    'level': status['status'],
                    'when': str(datetime.now()),
                })


def _depends():
    return ['AlertPlugin', 'VolumePlugin', 'ZfsPlugin']


def _init(dispatcher):

    def on_status_change(args):
        dispatcher.call_task_sync('alert.volumes.status')

    dispatcher.register_task_handler('alert.volumes.status', AlertVolumeStatusTask)

    on_status_change({})
