import enum
import functools
from typing import Awaitable, Callable

from middlewared.api.base import BaseModel, ForUpdateMetaclass
from middlewared.api.base.handler.accept import validate_model
from middlewared.api.base.handler.inspect import model_field_is_model, model_field_is_list_of_models
from middlewared.api.base.handler.model_provider import ModelProvider, ModelFactory
from middlewared.api.base.model import _NotRequired
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
        def _build_field_mapping(model: type[BaseModel]) -> tuple[dict[str, str], dict[str, str]]:
            """Build bidirectional mapping between field names and aliases."""
            alias_to_field = {}
            field_to_alias = {}
            for field_name, field_info in model.model_fields.items():
                alias = field_info.alias or field_name
                alias_to_field[alias] = field_name
                field_to_alias[field_name] = alias
            return alias_to_field, field_to_alias

        def _adapt_nested_value(val, current_field, new_field):
            """Adapt nested model values (dict or list of models)."""
            if isinstance(val, dict):
                if (
                    (current_nested := model_field_is_model(current_field, value_hint=val))
                    and (new_nested := model_field_is_model(new_field, name_hint=current_nested.__name__))
                    and current_nested.__name__ == new_nested.__name__
                ):
                    return self._adapt_value(val, current_nested, new_nested, direction)
            elif isinstance(val, list):
                if (
                    (current_nested := model_field_is_list_of_models(current_field))
                    and (current_nested := model_field_is_model(current_nested))
                    and (new_nested := model_field_is_list_of_models(new_field))
                    and (new_nested := model_field_is_model(new_nested))
                    and current_nested.__name__ == new_nested.__name__
                ):
                    return [self._adapt_value(v, current_nested, new_nested, direction) for v in val]
            return val

        # Build field mappings once
        current_alias_to_field, _ = _build_field_mapping(current_model)
        new_alias_to_field, new_field_to_alias = _build_field_mapping(new_model)

        # Track which fields are present to avoid duplicates
        present_fields = set()

        # Process existing keys in value
        for k in value.keys():
            current_field_name = current_alias_to_field.get(k, k)
            new_field_name = new_alias_to_field.get(k, k)

            # Check if field exists in both models
            if current_field_name in current_model.model_fields and new_field_name in new_model.model_fields:
                present_fields.add(new_field_name)

                # Adapt nested values
                current_field_info = current_model.model_fields[current_field_name]
                new_field_info = new_model.model_fields[new_field_name]
                value[k] = _adapt_nested_value(value[k], current_field_info.annotation, new_field_info.annotation)

                # Normalize key to preferred format for new model
                new_preferred_key = new_field_to_alias[new_field_name]
                if k != new_preferred_key and new_preferred_key not in value:
                    value[new_preferred_key] = value.pop(k)

        # Add missing fields with defaults (only for non-ForUpdate models)
        if new_model.__class__ is not ForUpdateMetaclass:
            for field_name, field_info in new_model.model_fields.items():
                if field_name not in present_fields and not field_info.is_required():
                    key_to_use = field_info.alias or field_name
                    value[key_to_use] = field_info.get_default(call_default_factory=True)

        match direction:
            case Direction.DOWNGRADE:
                value = current_model.to_previous(value)
            case Direction.UPGRADE:
                value = new_model.from_previous(value)

        for k, v in list(value.items()):
            if k in current_model.model_fields and k not in new_model.model_fields:
                value.pop(k)
            elif isinstance(v, (Undefined, _NotRequired)):
                value.pop(k)

        return value


async def async_validate_model(model: type[BaseModel], data: dict):
    return validate_model(model, data)
