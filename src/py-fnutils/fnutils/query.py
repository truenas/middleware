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
import inspect
import dateutil.parser


operators_table = {
    '=': lambda x, y: x == y,
    '!=': lambda x, y: x != y,
    '>': lambda x, y: x > y,
    '<': lambda x, y: x < y,
    '>=': lambda x, y: x >= y,
    '<=': lambda x, y: x <= y,
    '~': lambda x, y: re.match(x, y)
}

conversions_table = {
    'timestamp': lambda v: dateutil.parser.parse(v)
}


def wrap(obj):
    if hasattr(obj, '__getstate__'):
        obj = obj.__getstate__()

    if inspect.isgenerator(obj):
        obj = list(obj)

    if type(obj) in (QueryDict, QueryList):
        return obj

    if isinstance(obj, dict):
        return QueryDict(obj)

    if isinstance(obj, list):
        return QueryList(obj)

    return obj


class QueryList(list):
    def __init__(self, *args, **kwargs):
        super(QueryList, self).__init__(*args, **kwargs)
        for idx, v in enumerate(self):
                self[idx] = wrap(v)

    def __getitem__(self, item):
        if type(item) is str:
            if item.isdigit():
                return super(QueryList, self).__getitem__(int(item))

            left, sep, right = item.partition('.')
            return super(QueryList, self).__getitem__(left)[right]

        return super(QueryList, self).__getitem__(item)

    def __setitem__(self, key, value):
        value = wrap(value)

        if type(key) is str:
            if key.isdigit():
                super(QueryList, self).__setitem__(int(key), value)

            left, sep, right = key.partition('.')
            self[left][right] = value

        super(QueryList, self).__setitem__(key, value)

    def eval_logic_and(self, item, lst):
        for i in lst:
            if not self.eval_tuple(item, i):
                return False

        return True

    def eval_logic_or(self, item, lst):
        for i in lst:
            if self.eval_tuple(item, i):
                return True

        return False

    def eval_logic_nor(self, item, lst):
        for i in lst:
            if self.eval_tuple(item, i):
                return False

        return True

    def eval_logic_operator(self, item, *t):
        op, lst = t
        return getattr(self, 'eval_logic_{0}'.format(op))(item, lst)

    def eval_field_operator(self, item, t):
        left, op, right = t

        if len(t) == 4:
            right = conversions_table[t[3]](right)

        return operators_table[op](item[left], right)

    def eval_tuple(self, item, t):
        if len(t) == 2:
            return self.eval_logic_operator(item, t)

        if len(t) in (3, 4):
            return self.eval_field_operator(item, t)

    def query(self, *rules, **params):
        single = params.pop('single', False)
        count = params.pop('count', None)
        offset = params.pop('offset', None)
        limit = params.pop('limit', None)
        sort = params.pop('sort', None)
        dir = params.pop('dir', 'desc')
        result = []

        if len(rules) == 0:
            result = list(self)

        for i in self:
            fail = False
            for r in rules:
                if not self.eval_tuple(i, r):
                    fail = True
                    break

            if not fail:
                result.append(i)

        result.sort(key=lambda x: x[sort], reverse=True if dir == 'desc' else False)

        if offset:
            result = result[offset:]

        if limit:
            result = result[:limit]

        if not result and single:
            return None

        if single:
            return result[0]

        if count:
            return len(result)

        return result


class QueryDict(dict):
    def __init__(self, *args, **kwargs):
        super(QueryDict, self).__init__(*args, **kwargs)
        for k, v in self.items():
                self[k] = wrap(v)

    def __getitem__(self, item):
        if type(item) is not str:
            return super(QueryDict, self).__getitem__(item)

        if '.' not in item:
            return super(QueryDict, self).__getitem__(item)

        left, sep, right = item.partition('.')
        return super(QueryDict, self).__getitem__(left)[right]

    def __setitem__(self, key, value):
        value = wrap(value)

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
        return right in self[left]

    def get(self, k, d=None):
        return self[k] if k in self else d
