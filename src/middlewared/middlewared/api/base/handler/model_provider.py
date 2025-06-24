from abc import ABC, abstractmethod
import asyncio
from concurrent.futures import Executor
import importlib
import logging
from types import ModuleType
from typing import Callable

from middlewared.api.base import BaseModel

logger = logging.getLogger(__name__)


class ModelProvider(ABC):
    @abstractmethod
    def __init__(self):
        self.models: dict[str, type[BaseModel]]

    async def get_model(self, name: str) -> type[BaseModel]:
        """Get API model by name."""
        return self.models[name]


class ModuleModelProvider(ModelProvider):
    """
    Provides API models from specified module.
    """

    def __init__(self, module_name: str):
        """
        :param module_name: module that contains models
        """
        self.models = models_from_module(importlib.import_module(module_name))


class LazyModuleModelProvider(ModelProvider):
    """
    Lazy loads API models from specified module.
    """

    def __init__(self, executor: Executor, module_name: str):
        """
        :param executor: executor to run `importlib`
        :param module_name: module that contains models
        """
        self.executor = executor
        self.module_name = module_name
        self.lock = asyncio.Lock()
        self.models = None
        self.models_factories: dict[str, Callable[[], type[BaseModel]]] = {}

    async def get_model(self, name: str) -> type[BaseModel]:
        async with self.lock:
            if self.models is None:
                logger.debug(f"Importing {self.module_name!r}")
                module = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    importlib.import_module,
                    self.module_name,
                )

                self.models = models_from_module(module)

            try:
                return self.models[name]
            except KeyError:
                if model_factory := self.models_factories.get(name):
                    new_model = model_factory()  # We may raise another KeyError here.
                    self.models[name] = new_model
                    return new_model

                raise


def models_from_module(module: ModuleType) -> dict[str, type[BaseModel]]:
    return {
        model_name: model
        for model_name, model in [
            (model_name, getattr(module, model_name))
            for model_name in dir(module)
        ]
        if isinstance(model, type) and issubclass(model, BaseModel)
    }
