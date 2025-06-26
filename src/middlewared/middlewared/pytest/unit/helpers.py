import functools
from typing import TYPE_CHECKING, Callable
from unittest.mock import Mock

from middlewared.api.base.handler.model_provider import ModelProvider
from middlewared.utils.plugins import LoadPluginsMixin
if TYPE_CHECKING:
    from middlewared.api.base import BaseModel
    from middlewared.pytest.unit.middleware import Middleware
    from middlewared.service import Service, CompoundService


def load_compound_service(name: str) -> 'Callable[[Middleware], CompoundService]':
    lpm = LoadPluginsMixin()
    lpm.event_register = Mock()
    lpm.event_source_manager = Mock()
    lpm._load_plugins()
    service = lpm.get_service(name)
    return functools.partial(_compound_service_wrapper, service)


def _compound_service_wrapper(service: 'CompoundService', fake_middleware: 'Middleware') -> 'CompoundService':
    service.middleware = fake_middleware
    for part in service.parts:
        part.middleware = fake_middleware
    return service


def create_service(middleware: 'Middleware', cls: 'type[Service]') -> 'Service':
    service = cls(middleware)
    middleware._resolve_methods([service], [])
    return service


class TestModelProvider(ModelProvider):
    def __init__(self, models: 'dict[str, type[BaseModel]]'):
        self.models = models

    async def get_model(self, name: str) -> 'type[BaseModel]':
        return self.models[name]
