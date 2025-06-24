from abc import ABC, abstractmethod
import asyncio
from concurrent.futures import Executor
import functools
import importlib
import logging
from types import ModuleType
from typing import Any, Callable, TypeAlias

from middlewared.api.base import BaseModel

logger = logging.getLogger(__name__)


ModelFactory: TypeAlias = Callable[[type[BaseModel]], type[BaseModel]]


class ModelProvider(ABC):
    @abstractmethod
    def __init__(self):
        self.models: dict[str, type[BaseModel]]

    def register_model(self, model_cls: type[BaseModel], *extra: Any) -> None:
        """Register an API model.

        :param model_cls: The model class to register.
        :param *extra: Extra arguments are ignored.
        """
        self.models[model_cls.__name__] = model_cls

    async def get_model(self, name: str) -> type[BaseModel]:
        """Get API model by name.

        :param name: Name of the model.
        :return: The `BaseModel` class.
        :raise KeyError: `name` is not a model registered with this `ModelProvider`.
        """
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
        :param executor: Executor to run `importlib`.
        :param module_name: Name of a module that contains models.
        """
        self.executor = executor
        self.module_name = module_name
        self.lock = asyncio.Lock()
        self.models = {}
        self.models_factories: dict[str, Callable[[], type[BaseModel] | None]] = {}

    def register_model(self, model_cls: type[BaseModel], model_factory: ModelFactory, arg_model_name: str) -> None:
        """Register a model factory to be called on `get_model`.

        :param model_cls: The `BaseModel` class whose name should be used to register the model returned by
            `model_factory`.
        :param model_factory: A callable that returns the model.
        :param arg_model_name: Name of the model to pass to `model_factory`.
        """
        self.models_factories[model_cls.__name__] = functools.partial(
            _create_model, self, model_factory, arg_model_name
        )

    async def get_model(self, name: str) -> type[BaseModel]:
        """Retrieve an API model by its name.

        Load the models from the module that this `ModelProvider` is responsible for. Either return the model from that
        module or call the model factory that was registered with `name`.

        :param name: Name of the model or name that its model factory was registered with.
        :return: Either the model belonging to module `self.module_name` or the model returned by a model factory.
        :raise KeyError: `name` is not a model registered with this `ModelProvider`.
        """
        async with self.lock:
            if not self.models:
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
                    if new_model := model_factory():
                        self.models[name] = new_model
                        return new_model

                raise


def models_from_module(module: ModuleType) -> dict[str, type[BaseModel]]:
    """Get all `BaseModel` subclasses that belong to a module.

    :param module: The module object whose directory to iterate over.
    :return: Mapping of model names to their respective class objects.
    """
    return {
        model_name: model
        for model_name, model in [
            (model_name, getattr(module, model_name))
            for model_name in dir(module)
        ]
        if isinstance(model, type) and issubclass(model, BaseModel)
    }


def _create_model(
    model_provider: ModelProvider, model_factory: ModelFactory, arg_model_name: str
) -> type[BaseModel] | None:
    """Call a model factory.

    :param model_provider: An instance of `ModelProvider` that contains the model to pass to `model_factory`.
    :param model_factory: A callable that returns the model.
    :param arg_model_name: Name of the model to pass to `model_factory`.
    :return: Either the `BaseModel` class returned by `model_factory` or `None` if `arg_model_name` is not a registered
        model name with `model_provider`.
    """
    if arg := model_provider.models.get(arg_model_name):
        return model_factory(arg)
