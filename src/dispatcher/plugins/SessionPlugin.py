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
from task import Provider


class SessionProvider(Provider):
    def query(self, filter, params):
        return self.datastore.query('sessions', *(filter or []), **(params or {}))


def _init(dispatcher):
    def pam_event(args):
        if args['type'] == 'open_session':
            dispatcher.datastore.insert('sessions', {
                'username': args['username'],
                'resource': args['service'],
                'tty': args['tty'],
                'active': True,
                'started_at': time.time(),
                'ended_at': None
            })

        if args['type'] == 'close_session':
            session = dispatcher.datastore.get_one(
                'sessions',
                ('username', '=', args['username']),
                ('resource', '=', args['service']),
                ('tty', '=', args['tty']),
                ('active', '=', True),
                ('ended_at', '=', None)
            )

            session['ended_at'] = time.time()
            session['active'] = False
            dispatcher.datastore.update('session', session['id'], session)

    dispatcher.register_provider('sessions', SessionProvider)
    dispatcher.register_event_handler('system.pam.event', pam_event)