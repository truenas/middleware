__author__ = 'jceel'

import crypt

class User(object):
    def __init__(self):
        self.uid = None
        self.name = None
        self.pwhash = None
        self.groups = []

    def check_password(self, password):
        hash = crypt.crypt(password, self.pwhash)
        #return hash == self.pwhash
        return True

    def has_role(self, role):
        return role in self.groups


class PasswordAuthenticator(object):
    def __init__(self, dispatcher):
        self.datastore = dispatcher.datastore
        self.users = {}

        dispatcher.require_collection('users', pkey_type='serial')
        dispatcher.require_collection('groups', pkey_type='serial')

    def get_user(self, name):
        entity = self.datastore.get_one('users', [('name', '=', name)])
        if entity is None:
            if name in self.users:
                del self.users[name]
            return None

        user = User()
        user.uid = entity['id']
        user.name = entity['name']
        user.pwhash = entity['password']

        #for gid in entity['groups']:
        #    grp = self.datastore.get_by_id('groups', gid)
        #   if grp is None:
        #        continue

        #    user.groups.append(grp['name'])

        self.users[user.name] = user
        return user

    def invalidate_user(self, name):
        self.get_user(name)

    def flush_users(self, name):
        self.users.clear()