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

import re
from datastore import DatastoreException


class ConfigNode(object):
    def __init__(self, path, root):
        self.path = path
        self.root = root

    @property
    def value(self):
        return self.root.get(self.path)

    @value.setter
    def value(self, v):
        self.root.set(self.path, v)

    @property
    def has_children(self):
        return len(self.children) > 0

    @property
    def children(self):
        result = set()
        for i in self.root.list_children(self.path):
            matched = i['id'][len(self.path) + 1:]
            child = matched.partition('.')[0]
            if child:
                result.add(child)

        return result

    def __getstate__(self):
        if not self.has_children:
            return self.value

        return {k: self[k].__getstate__() for k in self.children}

    def __getitem__(self, item):
        return ConfigNode(self.path + '.' + item, self.root)

    def __setitem__(self, key, value):
        ConfigNode(self.path + '.' + key, self.root).value = value

    def __contains__(self, item):
        return item in self.children

    def __len__(self):
        return len(self.children)

    def update(self, obj):
        if not self.has_children:
            self.value = obj
        else:
            for k, v in obj.items():
                self[k].update(v)


class ConfigStore(object):
    def __init__(self, datastore):
        self.__datastore = datastore
        if not self.__datastore.collection_exists('config'):
            raise DatastoreException("'config' collection doesn't exist")

    @staticmethod
    def create(datastore):
        datastore.collection_create('config', 'ltree', 'config')

    def exists(self, key):
        return self.__datastore.exists('config', ('id', '=', key))

    def get(self, key, default=None):
        ret = self.__datastore.get_one('config', ('id', '=', key))
        return ret['value'] if ret is not None else default

    def set(self, key, value):
        self.__datastore.upsert('config', key, value, config=True)

    def list_children(self, key=None):
        if key is None:
            return self.__datastore.query('config', wrap=False)
        return self.__datastore.query('config', ('id', '~', key + '.*'), wrap=False)

    def children_dict(self, root):
        result = {}
        for item in self.__datastore.query('config', ('id', '~', re.escape(root) + '\.[a-zA-Z0-9_]+\.')):
            matched = item['id'][len(root) + 1:]
            key, _, value = matched.partition('.')

            if key not in result.keys():
                result[key] = {}

            result[key][value] = item['value']

        return result