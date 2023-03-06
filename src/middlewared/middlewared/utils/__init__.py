import asyncio
import logging
import re
import signal
import subprocess
import json
from datetime import datetime, timedelta
from functools import wraps, cache
from threading import Lock

from middlewared.service_exception import MatchNotFound
from middlewared.utils.threading import start_daemon_thread  # noqa

MID_PID = None
MIDDLEWARE_RUN_DIR = '/var/run/middleware'
BOOTREADY = f'{MIDDLEWARE_RUN_DIR}/.bootready'
MANIFEST_FILE = '/data/manifest.json'
BRAND = 'TrueNAS'
PRODUCT = 'SCALE'
BRAND_PRODUCT = f'{BRAND}-{PRODUCT}'
NULLS_FIRST = 'nulls_first:'
NULLS_LAST = 'nulls_last:'
REVERSE_CHAR = '-'

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
    input = kwargs.pop('input', None)
    if input is not None:
        kwargs['stdin'] = subprocess.PIPE
    abort_signal = kwargs.pop('abort_signal', signal.SIGKILL)
    proc = await asyncio.create_subprocess_exec(*args, **kwargs)
    try:
        stdout, stderr = await proc.communicate(input)
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


def casefold(obj):
    if obj is None:
        return None

    if isinstance(obj, str):
        return obj.casefold()

    if isinstance(obj, (list, tuple)):
        return [x.casefold() for x in obj]

    raise ValueError(f'{type(obj)}: support for casefolding object type not implemented.')


class filters(object):
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

    def validate_filters(self, filters):
        for f in filters:
            if len(f) == 2:
                op, value = f
                if op != 'OR':
                    raise ValueError(f'Invalid operation: {op}')

                if not value:
                    raise ValueError('OR filter requires at least one branch.')

                self.validate_filters(value)
                continue

            elif len(f) != 3:
                raise ValueError(f'Invalid filter {f}')

            op = f[1]
            if op[0] == 'C':
                op = op[1:]
                if op == '~':
                    raise ValueError('Invalid case-insensitive operation: {}'.format(f[1]))

            if op not in self.opmap:
                raise ValueError('Invalid operation: {}'.format(f[1]))

    def validate_options(self, options):
        if options is None:
            return ({}, [], [])

        if options.get('get') and options.get('limit', 0) > 1:
            raise ValueError(
                'Invalid options combination. `get` implies a single result.'
            )

        if options.get('get') and options.get('offset'):
            raise ValueError(
                'Invalid options combination. `get` implies a single result.'
            )

        select = options.get('select', [])
        order_by = options.get('order_by', [])

        return (options, select, order_by)

    def filterop(self, i, f, source_getter):
        name, op, value = f
        source = source_getter(i, name)

        if op[0] == 'C':
            fn = self.opmap[op[1:]]
            source = casefold(source)
            value = casefold(value)
        else:
            fn = self.opmap[op]

        if fn(source, value):
            return True

        return False

    def getter_fn(self, _list):
        if not _list:
            return None

        if isinstance(_list[0], dict):
            return get

        return getattr

    def do_filters(self, _list, filters, select, shortcircuit):
        rv = []

        getter = self.getter_fn(_list)
        for i in _list:
            valid = True
            for f in filters:
                if len(f) == 2:
                    # OR parsing
                    op, value = f
                    for f in value:
                        if self.filterop(i, f, getter):
                            break
                    else:
                        valid = False
                        break

                elif not self.filterop(i, f, getter):
                    valid = False
                    break

            if not valid:
                continue

            if select:
                entry = self.do_select([i], select)[0]
            else:
                entry = i

            rv.append(entry)
            if shortcircuit:
                break

        return rv

    def do_select(self, _list, select):
        rv = []
        for i in _list:
            entry = {}
            for s in select:
                if s in i:
                    entry[s] = i[s]
            rv.append(entry)

        return rv

    def do_count(self, rv):
        return len(rv)

    def order_nulls(self, _list, order):
        if order.startswith(REVERSE_CHAR):
            order = order[1:]
            reverse = True
        else:
            reverse = False

        nulls = []
        non_nulls = []
        for entry in _list:
            if entry[order] is None:
                nulls.append(entry)
            else:
                non_nulls.append(entry)

        non_nulls = sorted(non_nulls, key=lambda x: get(x, order), reverse=reverse)
        return (nulls, non_nulls)

    def order_no_null(self, _list, order):
        if order.startswith(REVERSE_CHAR):
            order = order[1:]
            reverse = True
        else:
            reverse = False

        return sorted(_list, key=lambda x: get(x, order), reverse=reverse)

    def do_order(self, rv, order_by):
        for o in order_by:
            if o.startswith(NULLS_FIRST):
                nulls, non_nulls = self.order_nulls(rv, o[len(NULLS_FIRST):])
                rv = nulls + non_nulls
            elif o.startswith(NULLS_LAST):
                nulls, non_nulls = self.order_nulls(rv, o[len(NULLS_LAST):])
                rv = non_nulls + nulls
            else:
                rv = self.order_no_null(rv, o)

        return rv

    def do_get(self, rv):
        try:
            return rv[0]
        except IndexError:
            raise MatchNotFound() from None

    def filter_list(self, _list, filters=None, options=None):
        options, select, order_by = self.validate_options(options)

        do_shortcircuit = options.get('get') and not order_by
        if filters:
            self.validate_filters(filters)
            rv = self.do_filters(_list, filters, select, do_shortcircuit)
            if do_shortcircuit:
                return self.do_get(rv)

        elif select:
            rv = self.do_select(_list, select)
        else:
            rv = _list

        if options.get('count') is True:
            return self.do_count(rv)

        rv = self.do_order(rv, order_by)

        if options.get('get') is True:
            return self.do_get(rv)

        if options.get('offset'):
            rv = rv[options['offset']:]

        if options.get('limit'):
            return rv[:options['limit']]

        return rv


filter_list = filters().filter_list


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


@cache
def sw_info():
    """Returns the various software information from the manifest file."""
    with open(MANIFEST_FILE) as f:
        manifest = json.load(f)
        version = manifest['version']
        return {
            'stable': 'MASTER' not in manifest['version'],
            'version': version,
            'fullname': f'{BRAND_PRODUCT}-{version}',
            'buildtime': manifest['buildtime'],
        }


def sw_buildtime():
    return sw_info()['buildtime']


def sw_version():
    return sw_info()['fullname']


def sw_version_is_stable():
    return sw_info()['stable']


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
