import asyncio
import logging
import re
import signal
import subprocess
import threading
from datetime import datetime, timedelta
from functools import wraps
from threading import Lock

from middlewared.service_exception import MatchNotFound
from middlewared.utils import osc

BUILDTIME = None
VERSION = None
MID_PID = None

logger = logging.getLogger(__name__)


def bisect(condition, iterable):
    a = []
    b = []
    for val in iterable:
        if condition(val):
            a.append(val)
        else:
            b.append(val)

    return a, b


def Popen(args, **kwargs):
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
    encoding = kwargs.pop('encoding', None)
    errors = kwargs.pop('errors', None) or 'strict'
    abort_signal = kwargs.pop('abort_signal', signal.SIGKILL)
    proc = await asyncio.create_subprocess_exec(*args, **kwargs)
    try:
        stdout, stderr = await proc.communicate()
    except asyncio.CancelledError:
        if abort_signal is not None:
            proc.send_signal(abort_signal)
        raise
    if encoding:
        if stdout is not None:
            stdout = stdout.decode(encoding, errors)
        if stderr is not None:
            stderr = stderr.decode(encoding, errors)
    cp = subprocess.CompletedProcess(args, proc.returncode, stdout=stdout, stderr=stderr)
    if check:
        cp.check_returncode()
    return cp


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
        path = 'foo\\.bar' returns '2'
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
        '^': lambda x, y: x is not None and x.startswith(y),
        '!^': lambda x, y: x is not None and not x.startswith(y),
        '$': lambda x, y: x is not None and x.endswith(y),
        '!$': lambda x, y: x is not None and not x.endswith(y),
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
        try:
            return rv[0]
        except IndexError:
            raise MatchNotFound()

    if options.get('offset'):
        rv = rv[options['offset']:]

    if options.get('limit'):
        return rv[:options['limit']]

    return rv


def filter_getattrs(filters):
    """
    Get a set of attributes in a filter list.
    """
    attrs = set()
    if not filters:
        return attrs

    f = filters.copy()
    while f:
        filter_ = f.pop()
        if len(filter_) == 2:
            f.append(filter_[1])
        elif len(filter_) == 3:
            attrs.add(filter_[0])
        else:
            raise ValueError('Invalid filter.')
    return attrs


def sw_buildtime():
    global BUILDTIME
    if BUILDTIME is None:
        version = osc.get_app_version()
        BUILDTIME = version['buildtime']
    return BUILDTIME


def sw_version():
    global VERSION
    if VERSION is None:
        version = osc.get_app_version()
        VERSION = version['fullname']
    return VERSION


def sw_version_is_stable():
    version = osc.get_app_version()
    return version['stable']


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
