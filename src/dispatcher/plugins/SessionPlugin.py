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

import time
from task import Provider, query
from dispatcher.rpc import (description, pass_sender, returns, accepts,
                            SchemaHelper as h)


@description("Provides Information about the current loggedin Session")
class SessionProvider(Provider):
    @query('session')
    def query(self, filter=None, params=None):
        return self.datastore.query('sessions',
                                    *(filter or []),
                                    **(params or {}))

    @accepts()
    @returns(h.array(h.ref('sessions')))
    @description("Returns the logged in and active user sessions" +
                 "Does not include the service sessions in this.")
    def get_live_user_sessions(self):
        live_user_session_ids = []
        for conn in self.dispatcher.ws_server.connections:
            # The if check for 'uid' below is to seperate the actuall gui/cli
            # users of the websocket connection from that of system services
            # like etcd, statd and so on.
            if hasattr(conn.user, 'uid'):
                live_user_session_ids.append(conn.session_id)
        return self.datastore.query('sessions',
                                    ('id',
                                     'in',
                                     live_user_session_ids),
                                    **({}))

    @description("Returns the loggedin user for the current session")
    @returns(str)
    @pass_sender
    def whoami(self, sender):
        return sender.user.name


def _init(dispatcher, plugin):
    def pam_event(args):
        if args['type'] == 'open_session':
            dispatcher.datastore.insert('sessions', {
                'username': args['username'],
                'resource': args['service'],
                'tty': args['tty'],
                'active': True,
                'started-at': time.time(),
                'ended-at': None
            })

        if args['type'] == 'close_session':
            session = dispatcher.datastore.get_one(
                'sessions',
                ('username', '=', args['username']),
                ('resource', '=', args['service']),
                ('tty', '=', args['tty']),
                ('active', '=', True),
                ('ended-at', '=', None)
            )

            session['ended-at'] = time.time()
            session['active'] = False
            dispatcher.datastore.update('session', session['id'], session)

    plugin.register_schema_definition('session', {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'resource': {'type': ['string', 'null']},
            'tty': {'type': ['string', 'null']},
            'active': {'type': 'boolean'},
            'started-at': {'type': 'integer'},
            'ended-at': {'type': 'integer'}
        }
    })

    plugin.register_provider('sessions', SessionProvider)
    plugin.register_event_handler('system.pam.event', pam_event)
