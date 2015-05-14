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
    RpcException,
    SchemaHelper as h,
    accepts,
    description,
    returns,
)
from task import Provider, Task, TaskException, VerifyException, query

registered_alerts = {}


@description('Provides access to the alert system')
class AlertsProvider(Provider):

    @query('alert')
    def query(self, filter=None, params=None):
        return self.datastore.query(
            'alerts', *(filter or []), **(params or {})
        )

    def dismiss(self, id):
        try:
            self.datastore.delete('alerts', id)
        except DatastoreException, e:
            raise TaskException(
                errno.EBADMSG,
                'Cannot delete alert: {0}'.format(str(e))
            )

    @accepts(h.ref('alert'))
    def emit(self, alert):
        alertprops = registered_alerts.get(alert['name'])
        if alertprops is None:
            raise RpcException(
                errno.ENOENT,
                "Alert {0} not registered".format(alert['name'])
            )

        # Try to find the first matching namespace
        emitters = None
        dot = alert['name'].split('.')
        for i in xrange(len(dot), 0, -1):
            namespace = '.'.join(dot[0:i])
            afilter = self.datastore.get_one(
                'alerts-filters', ('name', '=', namespace),
                ('severity', '=', alert['severity']),
            )
            if afilter:
                emitters = afilter['emitters']

        # If there are no filters configured, set default emitters
        if emitters is None:
            if alert['severity'] == 'CRITICAL':
                emitters = ['UI', 'Email']
            else:
                emitters = ['UI']

        if 'UI' in emitters:
            self.datastore.insert('alerts', alert)

    @returns(h.array(str))
    def get_registered_alerts(self):
        return registered_alerts

    @accepts(str)
    def register_alert(self, name, verbose_name=None):
        if name not in registered_alerts:
            registered_alerts[name] = {
                'name': name,
                'verbose_name': verbose_name,
            }


@description('Provides access to the alerts filters')
class AlertsFiltersProvider(Provider):

    @query('alert-filter')
    def query(self, filter=None, params=None):
        return self.datastore.query(
            'alerts-filters', *(filter or []), **(params or {})
        )


@accepts(h.ref('alert-filter'))
class AlertFilterCreateTask(Task):

    def describe(self, alertfilter):
        return 'Creating alert filter {0}'.format(alertfilter['name'])

    def verify(self, alertfilter):
        return []

    def run(self, alertfilter):
        id = self.datastore.insert('alerts-filters', alertfilter)

        self.dispatcher.dispatch_event('alerts.filters.changed', {
            'operation': 'create',
            'ids': [id]
        })


@accepts(str)
class AlertFilterDeleteTask(Task):

    def describe(self, id):
        alertfilter = self.datastore.get_by_id('alerts-filters', id)
        return 'Deleting alert filter {0}'.format(alertfilter['name'])

    def verify(self, id):

        alertfilter = self.datastore.get_by_id('alerts-filters', id)
        if alertfilter is None:
            raise VerifyException(
                errno.ENOENT,
                'Alert filter with ID {0} does not exists'.format(id)
            )

        return []

    def run(self, id):
        try:
            self.datastore.delete('alerts-filters', id)
        except DatastoreException, e:
            raise TaskException(
                errno.EBADMSG,
                'Cannot delete alert filter: {0}'.format(str(e))
            )

        self.dispatcher.dispatch_event('alerts.filters.changed', {
            'operation': 'delete',
            'ids': [id]
        })


@accepts(str, h.ref('alert-filter'))
class AlertFilterUpdateTask(Task):

    def describe(self, id, alertfilter):
        alertfilter = self.datastore.get_by_id('alerts-filters', id)
        return 'Updating alert filter {0}'.format(alertfilter['name'])

    def verify(self, id, updated_fields):
        return []

    def run(self, id, updated_fields):
        try:
            alertfilter = self.datastore.get_by_id('alerts-filters', id)
            alertfilter.update(updated_fields)
            self.datastore.update('alerts-filters', id, alertfilter)
        except DatastoreException, e:
            raise TaskException(
                errno.EBADMSG,
                'Cannot update alert filter: {0}'.format(str(e))
            )

        self.dispatcher.dispatch_event('alerts.filters.changed', {
            'operation': 'update',
            'ids': [id],
        })


def _init(dispatcher, plugin):

    plugin.register_schema_definition('alert', {
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'description': {'type': 'string'},
            'severity': {'type': 'string'},
            'when': {'type': 'string'},
        }
    })

    plugin.register_schema_definition('alert-filter', {
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'severity': {
                'type': 'array',
                'items': {'type': 'string'},
            },
            'emitters': {
                'type': 'array',
                'items': {'type': 'string'},
            },
        }
    })

    dispatcher.require_collection('alerts')
    dispatcher.require_collection('alerts-filters')

    # Register providers
    plugin.register_provider('alerts', AlertsProvider)
    plugin.register_provider('alerts.filters', AlertsFiltersProvider)

    # Register task handlers
    plugin.register_task_handler(
        'alerts.filters.create', AlertFilterCreateTask
    )
    plugin.register_task_handler(
        'alerts.filters.delete', AlertFilterDeleteTask
    )
    plugin.register_task_handler(
        'alerts.filters.update', AlertFilterUpdateTask
    )

    # Register event types
    plugin.register_event_type('alerts.filters.changed')
