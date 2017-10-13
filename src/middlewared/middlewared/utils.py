import asyncio
import sys
import subprocess
from datetime import datetime, timedelta
from functools import wraps
from threading import Lock


if '/usr/local/lib' not in sys.path:
    sys.path.append('/usr/local/lib')
from freenasOS import Configuration

VERSION = None


async def django_modelobj_serialize(middleware, obj, extend=None, field_prefix=None):
    from django.db.models.fields.related import ForeignKey
    from freenasUI.contrib.IPAddressField import (
        IPAddressField, IP4AddressField, IP6AddressField
    )
    data = {}
    for field in obj._meta.fields:
        name = field.name
        try:
            value = getattr(obj, name)
        except Exception as e:
            # If foreign key does not exist set it to None
            if isinstance(field, ForeignKey) and isinstance(e, field.rel.model.DoesNotExist):
                data[name] = None
                continue
            raise
        if field_prefix and name.startswith(field_prefix):
            name = name[len(field_prefix):]
        if isinstance(field, (
            IPAddressField, IP4AddressField, IP6AddressField
        )):
            data[name] = str(value)
        elif isinstance(field, ForeignKey):
            data[name] = await django_modelobj_serialize(middleware, value) if value is not None else value
        else:
            data[name] = value
    if extend:
        data = await middleware.call(extend, data)
    return data


def Popen(args, **kwargs):
    kwargs.setdefault('encoding', 'utf8')
    shell = kwargs.pop('shell', None)
    if shell:
        return asyncio.create_subprocess_shell(args, **kwargs)
    else:
        return asyncio.create_subprocess_exec(*args, **kwargs)


async def run(*args, **kwargs):
    kwargs.setdefault('stdout', subprocess.PIPE)
    kwargs.setdefault('stderr', subprocess.PIPE)
    check = kwargs.pop('check', True)
    proc = await asyncio.create_subprocess_exec(*args, **kwargs)
    stdout, stderr = await proc.communicate()
    cp = subprocess.CompletedProcess(args, proc.returncode, stdout=stdout, stderr=stderr)
    if check:
        cp.check_returncode()
    return cp


def filter_list(_list, filters=None, options=None):

    opmap = {
        '=': lambda x, y: x == y,
        '!=': lambda x, y: x != y,
        'in': lambda x, y: x in y,
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


def sw_version():
    global VERSION
    if VERSION is None:
        conf = Configuration.Configuration()
        sys_mani = conf.SystemManifest()
        if sys_mani:
            VERSION = sys_mani.Version()
    return VERSION


def sw_version_is_stable():
    conf = Configuration.Configuration()
    train = conf.CurrentTrain()
    if train and 'stable' in train.lower():
        return True
    else:
        return False


def is_empty(val):
    """
    A small utility function that check if the provided string is either None, '',
    or just a string containing only spaces
    """
    return val in [None, ''] or val.isspace()


class Nid(object):

    def __init__(self, _id):
        self._id = _id

    def __call__(self):
        num = self._id
        self._id += 1
        return num


class cache_with_autorefresh(object):
    """
    A decorator which caches the result of a function (with no arguments as yet)
    and returns the cache untill the autorefresh timeout is hit, upon which it
    call the function again and caches the result for future calls.
    """

    def __init__(self, seconds=0, minutes=0, hours=0):
        self.refresh_period = timedelta(
            seconds=seconds, minutes=minutes, hours=hours
        )
        self.cached_return = None
        self.first = True
        self.time_of_last_call = datetime.min
        self.lock = Lock()

    def __call__(self, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            now = datetime.now()
            time_since_last_call = now - self.time_of_last_call

            with self.lock:
                if time_since_last_call > self.refresh_period or self.first:
                    self.first = False
                    self.time_of_last_call = now
                    self.cached_return = fn(*args, **kwargs)

            return self.cached_return

        return wrapper
