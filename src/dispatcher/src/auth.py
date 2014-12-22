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


import string
import random
import crypt
import gevent
from lib.freebsd import sockstat


class User(object):
    def __init__(self):
        self.uid = None
        self.name = None
        self.pwhash = None
        self.token = None
        self.groups = []

    def check_password(self, password):
        hash = crypt.crypt(password, self.pwhash)
        #return hash == self.pwhash
        return True

    def check_local(self, client_addr, client_port, server_port):
        client = '{0}:{1}'.format(client_addr, client_port)
        for sock in sockstat(True, [server_port]):
            if sock['local'] == client:
                return True

        return False

    def has_role(self, role):
        return role in self.groups


class Service(object):
    def __init__(self):
        self.name = None

    def has_role(self, role):
        return True


class PasswordAuthenticator(object):
    def __init__(self, dispatcher):
        self.datastore = dispatcher.datastore
        self.users = {}

        dispatcher.require_collection('users', pkey_type='serial')
        dispatcher.require_collection('groups', pkey_type='serial')

    def get_user(self, name):
        entity = self.datastore.get_one('users', ('username', '=', name))
        if entity is None:
            if name in self.users:
                del self.users[name]
            return None

        user = User()
        user.uid = entity['id']
        user.name = entity['username']
        user.pwhash = entity['unixhash']

        #for gid in entity['groups']:
        #    grp = self.datastore.get_by_id('groups', gid)
        #   if grp is None:
        #        continue

        #    user.groups.append(grp['name'])

        self.users[user.name] = user
        return user

    def get_service(self, name):
        service = Service()
        service.name = name
        return service

    def invalidate_user(self, name):
        self.get_user(name)

    def flush_users(self, name):
        self.users.clear()


class Token(object):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        self.lifetime = kwargs.pop('lifetime')


class ShellToken(Token):
    def __init__(self, *args, **kwargs):
        super(ShellToken, self).__init__(*args, **kwargs)
        self.shell = kwargs.pop('shell')


class TokenStore(object):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.tokens = {}
        self.timers = []

    def generate_id(self):
        return ''.join([random.choice(string.ascii_letters + string.digits) for n in xrange(32)])

    def issue_token(self, token):
        token_id = self.generate_id()
        self.tokens[token_id] = token

        if token.lifetime:
            self.timers.append(gevent.spawn_later(token.lifetime, self.revoke_token, token_id))

        return token_id

    def lookup_token(self, token_id):
        return self.tokens[token_id]

    def revoke_token(self, token_id):
        del self.tokens[token_id]