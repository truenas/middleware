import asyncio
import ctypes
import ctypes.util
import imp
import inspect
import os
import pwd
import re
import sys
import subprocess
import threading
from datetime import datetime, timedelta
from itertools import chain
from functools import wraps
from threading import Lock


# For freenasOS
if '/usr/local/lib' not in sys.path:
    sys.path.append('/usr/local/lib')

BUILDTIME = None
VERSION = None


def django_modelobj_serialize(middleware, obj, extend=None, extend_context=None, extend_context_value=None,
                              field_prefix=None, select=None):
    from django.db.models.fields.related import ForeignKey, ManyToManyField
    from freenasUI.contrib.IPAddressField import (
        IPAddressField, IP4AddressField, IP6AddressField
    )
    data = {}
    for field in chain(obj._meta.fields, obj._meta.many_to_many):
        origname = field.name
        if field_prefix and origname.startswith(field_prefix):
            name = origname[len(field_prefix):]
        else:
            name = origname
        if select and name not in select:
            continue
        try:
            value = getattr(obj, origname)
        except Exception as e:
            # If foreign key does not exist set it to None
            if isinstance(field, ForeignKey) and isinstance(e, field.rel.model.DoesNotExist):
                data[name] = None
                continue
            raise
        if isinstance(field, (
            IPAddressField, IP4AddressField, IP6AddressField
        )):
            data[name] = str(value)
        elif isinstance(field, ForeignKey):
            data[name] = django_modelobj_serialize(middleware, value) if value is not None else value
        elif isinstance(field, ManyToManyField):
            data[name] = []
            for o in value.all():
                data[name].append(django_modelobj_serialize(middleware, o))
        else:
            data[name] = value
    if extend:
        if extend_context:
            data = middleware.call_sync(extend, data, extend_context_value)
        else:
            data = middleware.call_sync(extend, data)
    return data


def Popen(args, **kwargs):
    kwargs.setdefault('encoding', 'utf8')
    shell = kwargs.pop('shell', None)
    if shell:
        return asyncio.create_subprocess_shell(args, **kwargs)
    else:
        return asyncio.create_subprocess_exec(*args, **kwargs)


async def run(*args, **kwargs):
    if isinstance(args[0], list):
        args = tuple(args[0])
    kwargs.setdefault('stdout', subprocess.PIPE)
    kwargs.setdefault('stderr', subprocess.PIPE)
    check = kwargs.pop('check', True)
    proc = await asyncio.create_subprocess_exec(*args, **kwargs)
    stdout, stderr = await proc.communicate()
    if "encoding" in kwargs:
        if stdout is not None:
            stdout = stdout.decode(kwargs["encoding"], kwargs.get("errors") or "strict")
        if stderr is not None:
            stderr = stderr.decode(kwargs["encoding"], kwargs.get("errors") or "strict")
    cp = subprocess.CompletedProcess(args, proc.returncode, stdout=stdout, stderr=stderr)
    if check:
        cp.check_returncode()
    return cp


def setusercontext(user):
    libc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('c'))
    libutil = ctypes.cdll.LoadLibrary(ctypes.util.find_library('util'))
    libc.getpwnam.restype = ctypes.POINTER(ctypes.c_void_p)
    pwnam = libc.getpwnam(user)
    passwd = pwd.getpwnam(user)

    libutil.login_getpwclass.restype = ctypes.POINTER(ctypes.c_void_p)
    lc = libutil.login_getpwclass(pwnam)
    os.setgid(passwd.pw_gid)
    if lc and lc[0]:
        libutil.setusercontext(
            lc, pwnam, passwd.pw_uid, ctypes.c_uint(0x07ff)  # 0x07ff LOGIN_SETALL
        )
        libutil.login_close(lc)
    else:
        os.setgid(passwd.pw_gid)
        libc.setlogin(user)
        libc.initgroups(user, passwd.pw_gid)
        os.setuid(passwd.pw_uid)

    try:
        os.chdir(passwd.pw_dir)
    except Exception:
        os.chdir('/')


def partition(s):
    rv = ''
    while True:
        left, sep, right = s.partition('.')
        if not sep:
            return rv + left, right
        if left[-1] == '\\':
            rv += left[:-1] + sep
            s = right
        else:
            return rv + left, right


def get(obj, path):
    """
    Get a path in obj using dot notation

    e.g.
        obj = {'foo': {'bar': '1'}, 'foo.bar': '2', 'foobar': ['first', 'second', 'third']}

        path = 'foo.bar' returns '1'
        path = 'foo\.bar' returns '2'
        path = 'foobar.0' returns 'first'
    """
    right = path
    cur = obj
    while right:
        left, right = partition(right)
        if isinstance(cur, dict):
            cur = cur.get(left)
        elif isinstance(cur, (list, tuple)):
            left = int(left)
            cur = cur[left] if left < len(cur) else None
    return cur


def filter_list(_list, filters=None, options=None):

    opmap = {
        '=': lambda x, y: x == y,
        '!=': lambda x, y: x != y,
        '>': lambda x, y: x > y,
        '>=': lambda x, y: x >= y,
        '<': lambda x, y: x < y,
        '<=': lambda x, y: x <= y,
        '~': lambda x, y: re.match(y, x),
        'in': lambda x, y: x in y,
        'nin': lambda x, y: x not in y,
        'rin': lambda x, y: x is not None and y in x,
        'rnin': lambda x, y: x is not None and y not in x,
        '^': lambda x, y: x.startswith(y),
        '!^': lambda x, y: not x.startswith(y),
        '$': lambda x, y: x.endswith(y),
        '!$': lambda x, y: not x.endswith(y),
    }

    if filters is None:
        filters = {}
    if options is None:
        options = {}

    select = options.get('select')

    rv = []
    if filters:

        def filterop(f):
            if len(f) != 3:
                raise ValueError(f'Invalid filter {f}')
            name, op, value = f
            if op not in opmap:
                raise ValueError('Invalid operation: {}'.format(op))
            if isinstance(i, dict):
                source = get(i, name)
            else:
                source = getattr(i, name)
            if opmap[op](source, value):
                return True
            return False

        for i in _list:
            valid = True
            for f in filters:
                if len(f) == 2:
                    op, value = f
                    if op == 'OR':
                        for f in value:
                            if filterop(f):
                                break
                        else:
                            valid = False
                            break
                    else:
                        raise ValueError(f'Invalid operation: {op}')
                elif not filterop(f):
                    valid = False
                    break

            if not valid:
                continue
            if select:
                entry = {}
                for s in select:
                    if s in i:
                        entry[s] = i[s]
            else:
                entry = i
            rv.append(entry)
            if options.get('get') is True:
                return entry
    elif select:
        rv = []
        for i in _list:
            entry = {}
            for s in select:
                if s in i:
                    entry[s] = i[s]
            rv.append(entry)
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


def sw_buildtime():
    # Lazy import to avoid freenasOS configure logging for us
    from freenasOS import Configuration
    global BUILDTIME
    if BUILDTIME is None:
        conf = Configuration.Configuration()
        sys_mani = conf.SystemManifest()
        if sys_mani:
            BUILDTIME = sys_mani.TimeStamp()
    return BUILDTIME


def sw_version():
    # Lazy import to avoid freenasOS configure logging for us
    from freenasOS import Configuration
    global VERSION
    if VERSION is None:
        conf = Configuration.Configuration()
        sys_mani = conf.SystemManifest()
        if sys_mani:
            VERSION = sys_mani.Version()
    return VERSION


def sw_version_is_stable():
    # Lazy import to avoid freenasOS configure logging for us
    from freenasOS import Configuration
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


def start_daemon_thread(*args, daemon=True, **kwargs):
    t = threading.Thread(*args, daemon=daemon, **kwargs)
    t.start()
    return t


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


def load_modules(directory):
    for f in sorted(os.listdir(directory)):
        if not f.endswith('.py'):
            continue
        f = f[:-3]
        name = '.'.join(
            ['middlewared'] +
            os.path.relpath(directory, os.path.dirname(os.path.dirname(__file__))).split('/') +
            [f]
        )
        fp, pathname, description = imp.find_module(f, [directory])
        try:
            yield imp.load_module(name, fp, pathname, description)
        finally:
            if fp:
                fp.close()


def load_classes(module, base, blacklist):
    classes = []
    for attr in dir(module):
        attr = getattr(module, attr)
        if inspect.isclass(attr):
            if issubclass(attr, base):
                if attr is not base and attr not in blacklist:
                    classes.append(attr)

    return classes
