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

from dispatcher.rpc import (
    SchemaHelper as h,
    accepts,
    returns,
)
from task import (
    Provider, Task, query
)


class AlertProvider(Provider):

    @query('alert')
    def query(self, filter=None, params=None):
        return self.datastore.query(
            'alerts', *(filter or []), **(params or {})
        )

    @returns(h.array(str))
    def get_alert_plugins(self):
        return []


@accepts(str, h.ref('alert'))
class AlertEmitTask(Task):

    def describe(self, alert):
        return 'Emitting alert {0}'.format(alert['name'])

    def run(self, alert):
        self.datastore.insert('alerts', alert)


def _init(dispatcher):

    dispatcher.register_schema_definition('alert', {
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'description': {'type': 'string'},
            'level': {'type': 'string'},
            'when': {'type': 'string'},
        }
    })

    dispatcher.require_collection('alerts')
    dispatcher.register_provider('alerts', AlertProvider)

    dispatcher.register_task_handler('alert.emit', AlertEmitTask)
