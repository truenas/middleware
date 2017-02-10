import sys
import bsd
import subprocess

if '/usr/local/lib' not in sys.path:
    sys.path.append('/usr/local/lib')
from freenasOS import Configuration


def django_modelobj_serialize(middleware, obj, extend=None, field_suffix=None):
    from django.db.models.fields.related import ForeignKey
    from freenasUI.contrib.IPAddressField import (
        IPAddressField, IP4AddressField, IP6AddressField
    )
    data = {}
    for field in obj._meta.fields:
        value = getattr(obj, field.name)
        name = field.name
        if field_suffix and name.startswith(field_suffix):
            name = name[len(field_suffix):]
        if isinstance(field, (
            IPAddressField, IP4AddressField, IP6AddressField
        )):
            data[name] = str(value)
        elif isinstance(field, ForeignKey):
            data[name] = django_modelobj_serialize(middleware, value) if value is not None else value
        else:
            data[name] = value
    if extend:
        data = middleware.call(extend, data)
    return data


def Popen(*args, **kwargs):

    def preexec_fn():
        bsd.closefrom(3)

    if kwargs.get('close_fds') is True and 'preexec_fn' not in kwargs:
        kwargs['preexec_fn'] = preexec_fn
        kwargs['close_fds'] = False
    return subprocess.Popen(*args, **kwargs)


def filter_list(_list, filters=None, options=None):

    opmap = {
        '=': lambda x, y: x == y,
        '!=': lambda x, y: x != y,
    }

    if filters is None:
        filters = {}
    if options is None:
        options = {}

    rv = []
    if filters:
        for i in _list:
            valid = True
            for f in filters:
                if len(f) == 3:
                    name, op, value = f
                    if op not in opmap:
                        raise ValueError('Invalid operation: {}'.format(op))
                    if isinstance(i, dict):
                        source = i[name]
                    else:
                        source = getattr(i, name)
                    if not opmap[op](source, value):
                        valid = False
                        break
            if not valid:
                continue
            rv.append(i)
            if options.get('get') is True:
                return i
    else:
        rv = _list

    if options.get('count') is True:
        return len(rv)

    if options.get('order_by'):
        for o in options.get('order_by'):
            if o.startswith('-'):
                o = o[1:]
                reverse = True
            else:
                reverse = False
            rv = sorted(rv, key=lambda x: x[o], reverse=reverse)

    if options.get('get') is True:
        return rv[0]

    return rv


def sw_version_is_stable():

    conf = Configuration.Configuration()

    if 'stable' in conf.CurrentTrain().lower():
        return True
    else:
        return False


class Nid(object):

    def __init__(self, _id):
        self._id = _id

    def __call__(self):
        num = self._id
        self._id += 1
        return num
