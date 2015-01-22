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


import re
import gevent
from event import EventSource
from dispatcher.rpc import RpcException


class EntitySubscriberEventSource(EventSource):
    def __init__(self, dispatcher):
        super(EntitySubscriberEventSource, self).__init__(dispatcher)
        self.services = []

    def changed(self, service, event):
        ids = event['ids']
        operation = event['operation']

        self.logger.debug('Collection provided by service {0} changed'.format(service))

        gevent.spawn(self.fetch, service, operation, ids)

    def fetch(self, service, operation, ids):
        try:
            entities = self.dispatcher.call_sync('{0}.query'.format(service), [('id', 'in', ids)])
        except RpcException, e:
            self.logger.warn('Cannot fetch changed entities from service {0}: {1}'.format(service, str(e)))
            return

        self.dispatcher.dispatch_event('entity-subscriber.{0}.changed'.format(service), {
            'service': service,
            'operation': operation,
            'entities': entities
        })

    def enable(self, event):
        service = re.match(r'^entity-subscriber\.([\.\w]+)\.changed$', event).group(1)
        self.dispatcher.register_event_handler('{0}.changed'.format(service), lambda e: self.changed(service, e))

    def disable(self, event):
        service = re.match(r'^entity-subscriber\.([\.\w]+)\.changed$', event).group(1)
        self.dispatcher.unregister_event_handler('{0}.changed'.format(service), lambda e: self.changed(service, e))

    def run(self):
        # Scan through registered events for those ending with .changed
        for i in self.dispatcher.event_types.keys():
            service = i.rpartition('.')[0]
            self.dispatcher.register_event_type('entity-subscriber.{0}.changed'.format(service), self)
            self.logger.info('Registered subscriber for service {0}'.format(service))
            self.services.append(service)


def _init(dispatcher):
    dispatcher.register_event_source('entity-subscriber', EntitySubscriberEventSource)