import functools
import importlib.util
import os.path
from types import ModuleType
from typing import TYPE_CHECKING, Callable
from unittest.mock import Mock

from middlewared.api.base.handler.model_provider import ModelProvider
from middlewared.utils.plugins import LoadPluginsMixin

if TYPE_CHECKING:
    from middlewared.api.base import BaseModel
    from middlewared.pytest.unit.middleware import Middleware
    from middlewared.service import CompoundService, Service


def load_compound_service(name: str) -> 'Callable[[Middleware], CompoundService]':
    lpm = LoadPluginsMixin()
    lpm.event_register = Mock()
    lpm.event_source_manager = Mock()
    lpm._load_plugins(whitelist=[
        'middlewared.plugins.datastore',
        'middlewared.plugins.system_advanced',
        'middlewared.plugins.vm',
        'middlewared.plugins.zettarepl',
    ])
    service = lpm.get_service(name)
    return functools.partial(_compound_service_wrapper, service)


def _compound_service_wrapper(service: 'CompoundService', fake_middleware: 'Middleware') -> 'CompoundService':
    _patch_service_middleware(service, fake_middleware)
    if hasattr(service, 'parts'):
        for part in service.parts:
            _patch_service_middleware(part, fake_middleware)
    return service


def _patch_service_middleware(service: 'Service', fake_middleware: 'Middleware') -> None:
    service.middleware = fake_middleware
    if hasattr(service, 'context'):
        service.context.middleware = fake_middleware
    if hasattr(service, '_svc_part'):
        service._svc_part.middleware = fake_middleware


def create_service(middleware: 'Middleware', cls: 'type[Service]') -> 'Service':
    return cls(middleware)


def load_migration(name: str) -> ModuleType:
    """Import an alembic revision by its path under `alembic/versions`, without its suffix."""
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'alembic', 'versions', f'{name}.py')
    spec = importlib.util.spec_from_file_location(os.path.basename(name), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestModelProvider(ModelProvider):
    def __init__(self, models: 'dict[str, type[BaseModel]]'):
        self.models = models

    async def get_model(self, name: str) -> 'type[BaseModel]':
        return self.models[name]
