import asyncio
import importlib
import inspect
import itertools
import logging
import os
import sys
import re
import subprocess
import threading
from datetime import datetime, timedelta
from functools import wraps
from threading import Lock

from middlewared.schema import Schemas
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
    proc = await asyncio.create_subprocess_exec(*args, **kwargs)
    stdout, stderr = await proc.communicate()
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


def middleware_pid():
    global MID_PID
    if MID_PID is None:
        with open('/var/run/middlewared.pid', 'r') as f:
            MID_PID = int(f.read().strip())
    return MID_PID


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


def load_modules(directory, base=None, depth=0):
    directory = os.path.normpath(directory)
    if base is None:
        middlewared_root = os.path.dirname(os.path.dirname(__file__))
        if os.path.commonprefix((f'{directory}/', f'{middlewared_root}/')) == f'{middlewared_root}/':
            base = '.'.join(
                ['middlewared'] +
                os.path.relpath(directory, middlewared_root).split('/')
            )
        else:
            for new_module_path in sys.path:
                if os.path.commonprefix((f'{directory}/', f'{new_module_path}/')) == f'{new_module_path}/':
                    break
            else:
                new_module_path = os.path.dirname(directory)
                logger.debug("Registering new module path %r", new_module_path)
                sys.path.insert(0, new_module_path)

            base = '.'.join(os.path.relpath(directory, new_module_path).split('/'))

    _, dirs, files = next(os.walk(directory))

    for f in files:
        if not f.endswith('.py'):
            continue
        name = f[:-3]

        if any(name.endswith(f'_{suffix}') for suffix in ('base', 'freebsd', 'linux')):
            if name.rsplit('_', 1)[-1].upper() != osc.SYSTEM:
                continue

        if name == '__init__':
            mod_name = base
        else:
            mod_name = f'{base}.{name}'

        yield importlib.import_module(mod_name)

    for f in dirs:
        if depth > 0:
            if f.endswith(('_freebsd', '_linux')):
                if f.rsplit('_', 1)[-1].upper() != osc.SYSTEM:
                    continue
            path = os.path.join(directory, f)
            yield from load_modules(path, f'{base}.{f}', depth - 1)


def load_classes(module, base, blacklist):
    classes = []
    for attr in dir(module):
        attr = getattr(module, attr)
        if inspect.isclass(attr):
            if issubclass(attr, base):
                if attr is not base and attr not in blacklist:
                    classes.append(attr)

    return classes


class LoadPluginsMixin(object):

    def __init__(self, overlay_dirs=None):
        self.overlay_dirs = overlay_dirs or []
        self._schemas = Schemas()
        self._services = {}
        self._services_aliases = {}

    def _load_plugins(self, on_module_begin=None, on_module_end=None, on_modules_loaded=None):
        from middlewared.service import Service, CompoundService, CRUDService, ConfigService, SystemServiceService

        services = []
        main_plugins_dir = os.path.realpath(os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            '..',
            'plugins',
        ))
        plugins_dirs = [os.path.join(overlay_dir, 'plugins') for overlay_dir in self.overlay_dirs]
        plugins_dirs.insert(0, main_plugins_dir)
        for plugins_dir in plugins_dirs:

            if not os.path.exists(plugins_dir):
                raise ValueError(f'plugins dir not found: {plugins_dir}')

            for mod in load_modules(plugins_dir, depth=1):
                if on_module_begin:
                    on_module_begin(mod)

                services.extend(load_classes(mod, Service, (ConfigService, CRUDService, SystemServiceService)))

                if on_module_end:
                    on_module_end(mod)

        def key(service):
            return service._config.namespace
        for name, parts in itertools.groupby(sorted(set(services), key=key), key=key):
            parts = list(parts)

            if len(parts) == 1:
                service = parts[0](self)
            else:
                service = CompoundService(self, [part(self) for part in parts])

            self.add_service(service)

        if on_modules_loaded:
            on_modules_loaded()

        # Now that all plugins have been loaded we can resolve all method params
        # to make sure every schema is patched and references match
        self._resolve_methods()

    def _resolve_methods(self):
        from middlewared.schema import resolve_methods  # Lazy import so namespace match
        to_resolve = []
        for service in list(self._services.values()):
            for attr in dir(service):
                to_resolve.append(getattr(service, attr))
        resolve_methods(self._schemas, to_resolve)

    def add_service(self, service):
        self._services[service._config.namespace] = service
        if service._config.namespace_alias:
            self._services_aliases[service._config.namespace_alias] = service

    def get_service(self, name):
        service = self._services.get(name)
        if service:
            return service
        return self._services_aliases[name]

    def get_services(self):
        return self._services
