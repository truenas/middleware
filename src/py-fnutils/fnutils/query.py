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


operators_table = {
    '=': lambda x, y: x == y,
    '!=': lambda x, y: x != y,
    '>': lambda x, y: x > y,
    '<': lambda x, y: x < y,
    '>=': lambda x, y: x >= y,
    '<=': lambda x, y: x <= y,
    '~': lambda x, y: re.match(x, y)
}


class QueryList(list):
    def __init__(self, *args, **kwargs):
        super(QueryList, self).__init__(*args, **kwargs)
        for idx, v in enumerate(self):
            if type(v) is dict:
                self[idx] = QueryDict(v)

            if type(v) is list:
                self[idx] = QueryList(v)

    def __getitem__(self, item):
        if type(item) is str:
            if item.isdigit():
                return super(QueryList, self).__getitem__(int(item))

            left, sep, right = item.partition('.')
            return super(QueryList, self).__getitem__(left)[right]

        return super(QueryList, self).__getitem__(item)

    def __setitem__(self, key, value):
        if type(value) is list:
            value = QueryList(value)

        if type(value) is dict:
            value = QueryDict(value)

        if type(key) is str:
            if key.isdigit():
                super(QueryList, self).__setitem__(int(key), value)

            left, sep, right = key.partition('.')
            self[left][right] = value

        super(QueryList, self).__setitem__(key, value)

    def __contains__(self, item):
        if type(item) is str:
            if item.isdigit():
                return super(QueryList, self).__contains__(int(item))

            left, sep, right = item.partition('.')
            return super(QueryList, self).__contains__(left)[right]

        return super(QueryList, self).__contains__(item)

    def query(self, *rules, **params):
        single = params.pop('single', False)
        result = []

        if len(rules) == 0:
            return list(self)

        for i in self:
            fail = False
            for left, op, right in rules:
                value = i[left]
                operator = operators_table[op]

                if operator(value, right):
                    continue

                fail = True

            if not fail:
                if single:
                    return i

                result.append(i)

        return result


class QueryDict(dict):
    def __init__(self, *args, **kwargs):
        super(QueryDict, self).__init__(*args, **kwargs)
        for k, v in self.items():
            if type(v) is dict:
                self[k] = QueryDict(v)

            if type(v) is list:
                self[k] = QueryList(v)

    def __getitem__(self, item):
        if type(item) is not str:
            return super(QueryDict, self).__getitem__(item)

        if '.' not in item:
            return super(QueryDict, self).__getitem__(item)

        left, sep, right = item.partition('.')
        return super(QueryDict, self).__getitem__(left)[right]

    def __setitem__(self, key, value):
        if type(value) is list:
            value = QueryList(value)

        if type(value) is dict:
            value = QueryDict(value)

        if type(key) is not str:
            return super(QueryDict, self).__setitem__(key, value)

        if '.' not in key:
            return super(QueryDict, self).__setitem__(key, value)

        left, sep, right = key.partition('.')
        self[left][right] = value

    def __contains__(self, item):
        if type(item) is not str:
            return super(QueryDict, self).__contains__(item)

        if '.' not in item:
            return super(QueryDict, self).__contains__(item)

        left, sep, right = item.partition('.')
        return super(QueryDict, self).__contains__(left)[right]

    def get(self, k, d=None):
        return self[k] if k in self else d
