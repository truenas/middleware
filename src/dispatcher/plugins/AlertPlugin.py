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
import errno

from datastore import DatastoreException
from dispatcher.rpc import (
    SchemaHelper as h,
    accepts,
    description,
    returns,
)
from task import Provider, Task, TaskException, VerifyException, query

registered_alerts = []


@description('Provides access to the alert system')
class AlertProvider(Provider):

    @query('alert')
    def query(self, filter=None, params=None):
        return self.datastore.query(
            'alerts', *(filter or []), **(params or {})
        )

    @query('alert-filter')
    def query_filters(self, filter=None, params=None):
        return self.datastore.query(
            'alerts-filters', *(filter or []), **(params or {})
        )

    @accepts(h.ref('alert'))
    def emit(self, alert):
        self.datastore.insert('alerts', alert)

    @returns(h.array(str))
    def get_registered_alerts(self):
        return registered_alerts

    @accepts(str)
    def register_alert(self, name):
        if name not in registered_alerts:
            registered_alerts.append(name)


@accepts(h.ref('alert-filter'))
class AlertFilterCreateTask(Task):

    def describe(self, alertfilter):
        return 'Creating alert filter {0}'.format(alertfilter['name'])

    def verify(self, alertfilter):
        return ['system']

    def run(self, alertfilter):
        self.datastore.insert('alertsfilters', alertfilter)

        #self.dispatcher.dispatch_event('alerts.filters.changed', {
        #    'operation': 'create',
        #    'ids': [alertfilter['name']]
        #})


@accepts(int)
class AlertFilterDeleteTask(Task):

    def describe(self, uid):
        alertfilter = self.datastore.get_by_id('alertsfilters', uid)
        return 'Deleting alert filter {0}'.format(alertfilter['name'])

    def verify(self, uid):

        alertfilter = self.datastore.get_by_id('alertsfilters', uid)
        if alertfilter is None:
            raise VerifyException(
                errno.ENOENT,
                'Alert filter with ID {0} does not exists'.format(uid)
            )

        return ['system']

    def run(self, uid):
        try:
            self.datastore.delete('alertsfilters', uid)
        except DatastoreException, e:
            raise TaskException(
                errno.EBADMSG,
                'Cannot delete alert filter: {0}'.format(str(e))
            )


@accepts(int, h.ref('alert-filter'))
class AlertFilterUpdateTask(Task):

    def describe(self, uid, alertfilter):
        return 'Updating alert filter {0}'.format(alertfilter['name'])

    def verify(self, uid, updated_fields):
        return ['system']

    def run(self, uid, updated_fields):
        try:
            alertfilter = self.datastore.get_by_id('alertsfilters', uid)
            alertfilter.update(updated_fields)
            self.datastore.update('alertsfilters', uid, alertfilter)
        except DatastoreException, e:
            raise TaskException(
                errno.EBADMSG,
                'Cannot update alert filter: {0}'.format(str(e))
            )


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

    dispatcher.register_schema_definition('alert-filter', {
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'emitters': {'type': 'array'},
        }
    })

    dispatcher.require_collection('alerts')
    dispatcher.require_collection('alerts-filters')
    dispatcher.register_provider('alerts', AlertProvider)

    # Register task handlers
    dispatcher.register_task_handler(
        'alerts.filters.create', AlertFilterCreateTask
    )
    dispatcher.register_task_handler(
        'alerts.filters.delete', AlertFilterDeleteTask
    )
    dispatcher.register_task_handler(
        'alerts.filters.update', AlertFilterUpdateTask
    )

    # Register event types
    dispatcher.register_event_type('alerts.filters.changed')
