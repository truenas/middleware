import importlib
import inspect
import itertools
import logging
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from middlewared.service import Service

logger = logging.getLogger(__name__)


def load_modules(directory, base=None, depth=0, whitelist=None):
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
    for f in filter(lambda x: x[-3:] == '.py', files):
        module_name = base if f == '__init__.py' else f'{base}.{f[:-3]}'
        if whitelist is None or any(module_name.startswith(w) for w in whitelist):
            yield importlib.import_module(module_name)

    for f in dirs:
        if depth > 0:
            path = os.path.join(directory, f)
            yield from load_modules(path, f'{base}.{f}', depth - 1, whitelist)


def load_classes(module, base, blacklist):
    classes = []
    for attr in dir(module):
        attr = getattr(module, attr)
        if inspect.isclass(attr):
            if issubclass(attr, base):
                if attr is not base and attr not in blacklist:
                    classes.append(attr)

    return classes


class LoadPluginsMixin:

    def __init__(self):
        self._services: dict[str, 'Service'] = {}
        self._services_aliases: dict[str, 'Service'] = {}
        super().__init__()

    def _load_plugins(self, on_module_begin=None, on_module_end=None, on_modules_loaded=None, whitelist=None,
                      service_container=None):
        from middlewared.service import Service, CompoundService, ABSTRACT_SERVICES

        services = []
        plugins_dir = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'plugins'))
        if not os.path.exists(plugins_dir):
            raise ValueError(f'plugins dir not found: {plugins_dir}')

        for mod in load_modules(plugins_dir, depth=1, whitelist=whitelist):
            if on_module_begin:
                on_module_begin(mod)

            services.extend(load_classes(mod, Service, ABSTRACT_SERVICES))

            if on_module_end:
                on_module_end(mod)

        def key(service):
            return service._config.namespace

        for name, parts in itertools.groupby(sorted(set(services), key=key), key=key):
            service = service_container
            for name_part in name.split("."):
                if (service := getattr(service, name_part, None)) is None:
                    break
            if service is not None and not isinstance(service, Service):
                service = None

            if service is None:
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

    def add_service(self, service: 'Service'):
        self._services[service._config.namespace] = service
        if service._config.namespace_alias:
            self._services_aliases[service._config.namespace_alias] = service

    def get_service(self, name: str) -> 'Service':
        service = self._services.get(name)
        if service:
            return service
        return self._services_aliases[name]

    def get_services(self):
        return self._services
