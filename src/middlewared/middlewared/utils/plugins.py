import importlib
import inspect
import itertools
import logging
import os
import sys

from middlewared.schema import Schemas
from middlewared.utils import osc

logger = logging.getLogger(__name__)


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
        from middlewared.service import Service, CompoundService, ABSTRACT_SERVICES

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

                services.extend(load_classes(mod, Service, ABSTRACT_SERVICES))

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

            if not service._config.private and not service._config.cli_private and not service._config.cli_namespace:
                raise RuntimeError(f'Service {service!r} does not have CLI namespace set')

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
