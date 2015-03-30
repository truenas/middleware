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

import errno
import time
import gevent
from dispatcher.rpc import RpcException, pass_sender, accepts, returns, private
from dispatcher.rpc import SchemaHelper as h
from task import Provider
from fnutils import first_or_default


transactions = {}


class Transaction(object):
    def __init__(self, identifier):
        self.identifier = identifier
        self.sessions = []

    def __getstate__(self):
        return {
            'identifier': self.identifier,
            'sessions': self.sessions
        }

    def purge(self, session):
        self.sessions.remove(session)


class Session(object):
    def __init__(self, timeout, sid, user):
        self.started_at = time.time()
        self.timeout = timeout
        self.sid = sid
        self.user = user

    def __getstate__(self):
        return {
            'started-at': self.started_at,
            'timeout': self.timeout,
            'sid': self.sid,
            'user': self.user
        }


class UITransactionProvider(Provider):
    @pass_sender
    @accepts(str, int)
    @returns(bool)
    def acquire(self, identifier, timeout, sender):
        t = transactions.setdefault(identifier, Transaction(identifier))
        s = first_or_default(lambda s: s.sid == sender.session_id, t)

        if s:
            raise RpcException(errno.EBUSY, 'Transaction is already held by current session')

        s = Session(timeout, sender.user.name, sender.session_id)
        t.sessions.append(s)
        gevent.spawn(t.purge, s)

    @pass_sender
    @accepts(str)
    def release(self, identifier, sender):
        if identifier not in transactions:
            raise RpcException(errno.ENOENT, 'Transaction not found')

        t = transactions[identifier]
        s = first_or_default(lambda s: s.sid == sender.session_id, t)

        if not s:
            raise RpcException(errno.EINVAL, 'Transaction is not held by current session')

        t.purge(s)

    @pass_sender
    @accepts(str)
    def query(self, identifier, sender):
        if identifier not in transactions:
            return None

        return transactions[identifier]

    @private
    def dump(self):
        return transactions


def _init(dispatcher):
    dispatcher.register_schema_definition('ui-transaction', {
        'type': 'object',
        'properties': {
            'identifier': {'type': 'string'},
            'sessions': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'started-at': {'type': 'number'},
                        'timeout': {'type': 'number'},
                        'sid': {'type': 'number'},
                        'user': {'type': 'string'}
                    }
                }
            }
        }
    })

    dispatcher.register_provider('ui.transactions', UITransactionProvider)