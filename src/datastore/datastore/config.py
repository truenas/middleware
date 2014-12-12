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


class ConfigStore(object):
    def __init__(self, datastore):
        self.__datastore = datastore
        if not self.__datastore.collection_exists('config'):
            raise DatastoreException("'config' collection doesn't exist")

    @staticmethod
    def create(datastore):
        datastore.collection_create('config', 'ltree', 'config')

    def get(self, key, default=None):
        ret = self.__datastore.get_one('config', ('id', '=', key))
        return ret['value'] if ret is not None else default

    def set(self, key, value):
        self.__datastore.upsert('config', key, value)

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