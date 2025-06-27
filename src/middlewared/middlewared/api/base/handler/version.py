import enum
import functools
from typing import Awaitable, Callable

from middlewared.api.base import BaseModel, ForUpdateMetaclass
from .accept import validate_model
from .inspect import model_field_is_model, model_field_is_list_of_models
from .model_provider import ModelProvider, ModelFactory
from middlewared.utils.lang import Undefined


class Direction(enum.StrEnum):
    DOWNGRADE = "DOWNGRADE"
    UPGRADE = "UPGRADE"


class APIVersionDoesNotExistException(Exception):
    def __init__(self, version: str):
        self.version = version
        super().__init__(f"API Version {self.version!r} does not exist")


class APIVersionDoesNotContainModelException(Exception):
    def __init__(self, version: str, model_name: str):
        self.version = version
        self.model_name = model_name
        super().__init__(f"API version {version!r} does not contain model {model_name!r}")


class APIVersion:
    def __init__(self, version: str, model_provider: ModelProvider):
        """
        :param version: API version name
        :param model_provider: `ModelProvider` instance
        """
        self.version: str = version
        self.model_provider: ModelProvider = model_provider

    def __repr__(self):
        return f"<APIVersion {self.version}>"

    async def get_model(self, name: str) -> type[BaseModel]:
        """Get API model by name.

        :param name:
        :return: The API model registered with `name`.
        :raise APIVersionDoesNotContainModelException: `arg_model_name` not found in this API version.
        """
        try:
            return await self.model_provider.get_model(name)
        except KeyError:
            raise APIVersionDoesNotContainModelException(self.version, name) from None

    def register_model(self, model_cls: type[BaseModel], model_factory: ModelFactory, arg_model_name: str) -> None:
        """Store an API method to be retrieved later by `get_model`.

        :param model_cls: The `BaseModel` class to register.
        :param model_factory: A callable that returns the `BaseModel` when `LazyModuleModelProvider` is used.
        :param arg_model_name: Name of the model to pass to `model_factory`.
        """
        self.model_provider.register_model(model_cls, model_factory, arg_model_name)


class APIVersionsAdapter:
    """
    Converts method parameters and return results between different API versions.
    """

    def __init__(self, versions: list[APIVersion]):
        """
        :param versions: A chronologically sorted list of API versions.
        """
        self.versions: dict[str, APIVersion] = {version.version: version for version in versions}
        self.versions_history: list[str] = list(self.versions.keys())
        self.current_version: str = self.versions_history[-1]

    async def adapt(self, value: dict, model_name: str, version1: str, version2: str) -> dict:
        """
        Adapts `value` (that matches a model identified by `model_name`) from API `version1` to API `version2`).

        :param value: a value to convert
        :param model_name: a name of the model. Must exist in all API versions, including intermediate ones, or
            `APIVersionDoesNotContainModelException` will be raised.
        :param version1: original API version from which the `value` comes from
        :param version2: target API version that needs `value`
        :return: converted value
        :raise APIVersionDoesNotExistException:
        :raise APIVersionDoesNotContainModelException:
        """
        return (await self.adapt_model(value, model_name, version1, version2))[1]

    async def adapt_model(
        self,
        value: dict,
        model_name: str,
        version1: str,
        version2: str,
    ) -> tuple[type[BaseModel] | None, dict]:
        """
        Same as `adapt`, but returned value will be a tuple of `version2` model instance and converted value.

        :raise APIVersionDoesNotExistException:
        :raise APIVersionDoesNotContainModelException:
        """
        try:
            version1_index = self.versions_history.index(version1)
        except ValueError:
            raise APIVersionDoesNotExistException(version1) from None

        try:
            version2_index = self.versions_history.index(version2)
        except ValueError:
            raise APIVersionDoesNotExistException(version2) from None

        current_version = self.versions[version1]
        current_version_model = await current_version.get_model(model_name)

        value_factory = functools.partial(async_validate_model, current_version_model, value)
        model = current_version_model

        if version1_index < version2_index:
            step = 1
            direction = Direction.UPGRADE
        else:
            step = -1
            direction = Direction.DOWNGRADE

        for version_index in range(version1_index + step, version2_index + step, step):
            new_version = self.versions[self.versions_history[version_index]]

            value_factory = functools.partial(
                self._adapt_model, value_factory, model_name, current_version, new_version, direction,
            )
            try:
                model = await new_version.get_model(model_name)
            except APIVersionDoesNotContainModelException:
                model = None

            current_version = new_version

        return model, await value_factory()

    async def _adapt_model(
        self,
        value_factory: Callable[[], Awaitable[dict]],
        model_name: str,
        current_version: APIVersion,
        new_version: APIVersion,
        direction: Direction,
    ):
        """
        :raise APIVersionDoesNotContainModelException:
        """
        current_model = await current_version.get_model(model_name)
        new_model = await new_version.get_model(model_name)
        return self._adapt_value(await value_factory(), current_model, new_model, direction)

    def _adapt_value(
        self,
        value: dict,
        current_model: type[BaseModel],
        new_model: type[BaseModel],
        direction: Direction,
    ):
        for k in value:
            if k in current_model.model_fields and k in new_model.model_fields:
                current_model_field = current_model.model_fields[k].annotation
                new_model_field = new_model.model_fields[k].annotation
                if (
                    isinstance(value[k], dict) and
                    (current_nested_model := model_field_is_model(current_model_field, value_hint=value[k])) and
                    (new_nested_model := model_field_is_model(new_model_field,
                                                              name_hint=current_nested_model.__name__)) and
                    current_nested_model.__name__ == new_nested_model.__name__
                ):
                    value[k] = self._adapt_value(value[k], current_nested_model, new_nested_model, direction)
                elif (
                    isinstance(value[k], list) and
                    (current_nested_model := model_field_is_list_of_models(current_model_field)) and
                    (current_nested_model := model_field_is_model(current_nested_model)) and
                    (new_nested_model := model_field_is_list_of_models(new_model_field)) and
                    (new_nested_model := model_field_is_model(new_nested_model)) and
                    current_nested_model.__name__ == new_nested_model.__name__
                ):
                    value[k] = [
                        self._adapt_value(v, current_nested_model, new_nested_model, direction)
                        for v in value[k]
                    ]

        if new_model.__class__ is not ForUpdateMetaclass:
            for k, field in new_model.model_fields.items():
                if k not in value and not field.is_required():
                    value[k] = field.get_default()

        match direction:
            case Direction.DOWNGRADE:
                value = current_model.to_previous(value)
            case Direction.UPGRADE:
                value = new_model.from_previous(value)

        for k in list(value):
            if k in current_model.model_fields and k not in new_model.model_fields:
                value.pop(k)

        for k, v in list(value.items()):
            if isinstance(v, Undefined):
                value.pop(k)

        return value


async def async_validate_model(model: type[BaseModel], data: dict):
    return validate_model(model, data)
