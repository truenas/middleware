import asyncio
from concurrent.futures import Executor
import importlib
import logging
from types import ModuleType

from middlewared.api.base import BaseModel

logger = logging.getLogger(__name__)


class ModelProvider:
    async def get_model(self, name: str) -> type[BaseModel]:
        """
        Get API model by name
        :param name:
        :return: model
        """
        raise NotImplementedError


class ModuleModelProvider(ModelProvider):
    """
    Provides API models from specified module.
    """
    def __init__(self, module: ModuleType):
        """
        :param module: module that contains models
        """
        self.models = models_from_module(module)

    async def get_model(self, name: str) -> type[BaseModel]:
        return self.models[name]


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
        self.models_factories = {}

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
                # FIXME: Please see `Middleware.__initialize`
                if model_factory := self.models_factories.get(name):
                    new_model = model_factory()
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
