import enum
from types import ModuleType

from middlewared.api.base import BaseModel, ForUpdateMetaclass
from .accept import validate_model
from .inspect import model_field_is_model, model_field_is_list_of_models


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
    def __init__(self, version: str, models: dict[str, type[BaseModel]]):
        """
        :param version: API version name
        :param models: a dictionary which keys are model names and values are models used in the API version
        """
        self.version: str = version
        self.models: dict[str, type[BaseModel]] = models

    @classmethod
    def from_module(cls, version: str, module: ModuleType) -> "APIVersion":
        """
        Create `APIVersion` from a module (e.g. `middlewared.api.v25_04_0`).
        :param version: API version name
        :param module: module object
        :return: `APIVersion` instance
        """
        return cls(
            version,
            {
                model_name: model
                for model_name, model in [
                    (model_name, getattr(module, model_name))
                    for model_name in dir(module)
                ]
                if isinstance(model, type) and issubclass(model, BaseModel)
            },
        )

    def __repr__(self):
        return f"<APIVersion {self.version}>"


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

    def adapt(self, value: dict, model_name: str, version1: str, version2: str) -> dict:
        """
        Adapts `value` (that matches a model identified by `model_name`) from API `version1` to API `version2`).

        :param value: a value to convert
        :param model_name: a name of the model. Must exist in all API versions, including intermediate ones, or
            `APIVersionDoesNotContainModelException` will be raised.
        :param version1: original API version from which the `value` comes from
        :param version2: target API version that needs `value`
        :return: converted value
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
        try:
            current_version_model = current_version.models[model_name]
        except KeyError:
            raise APIVersionDoesNotContainModelException(current_version.version, model_name)
        value = validate_model(current_version_model, value)

        if version1_index < version2_index:
            step = 1
            direction = Direction.UPGRADE
        else:
            step = -1
            direction = Direction.DOWNGRADE

        for version_index in range(version1_index + step, version2_index + step, step):
            new_version = self.versions[self.versions_history[version_index]]

            value = self._adapt_model(value, model_name, current_version, new_version, direction)

            current_version = new_version

        return value

    def _adapt_model(self, value: dict, model_name: str, current_version: APIVersion, new_version: APIVersion,
                     direction: Direction):
        try:
            current_model = current_version.models[model_name]
        except KeyError:
            raise APIVersionDoesNotContainModelException(current_version.version, model_name) from None

        try:
            new_model = new_version.models[model_name]
        except KeyError:
            raise APIVersionDoesNotContainModelException(new_version.version, model_name) from None

        return self._adapt_value(value, current_model, new_model, direction)

    def _adapt_value(self, value: dict, current_model: type[BaseModel], new_model: type[BaseModel],
                     direction: Direction):
        for k in value:
            if k in current_model.model_fields and k in new_model.model_fields:
                current_model_field = current_model.model_fields[k].annotation
                new_model_field = new_model.model_fields[k].annotation
                if (
                    isinstance(value[k], dict) and
                    (current_nested_model := model_field_is_model(current_model_field)) and
                    (new_nested_model := model_field_is_model(new_model_field)) and
                    current_nested_model.__class__.__name__ == new_nested_model.__class__.__name__
                ):
                    value[k] = self._adapt_value(value[k], current_nested_model, new_nested_model, direction)
                elif (
                    isinstance(value[k], list) and
                    (current_nested_model := model_field_is_list_of_models(current_model_field)) and
                    (current_nested_model := model_field_is_model(current_nested_model)) and
                    (new_nested_model := model_field_is_list_of_models(new_model_field)) and
                    (new_nested_model := model_field_is_model(new_nested_model)) and
                    current_nested_model.__class__.__name__ == new_nested_model.__class__.__name__
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

        return value
