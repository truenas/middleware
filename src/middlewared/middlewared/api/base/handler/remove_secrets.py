import typing

from pydantic import Discriminator, Secret
from pydantic.fields import FieldInfo

from middlewared.api.base import SECRET_VALUE, BaseModel

from .inspect import (
    model_field_is_dict_of_models,
    model_field_is_list_of_models,
    model_field_is_model,
    unpack_union_model_field,
)

__all__ = ["remove_secrets"]


def remove_secrets(model: type[BaseModel], value: typing.Any, discriminator: str | None = None) -> typing.Any:
    """
    Removes `Secret` values from a model value.
    :param model: `BaseModel` that corresponds to `value`.
    :param value: value that potentially contains `Secret` data.
    :param discriminator: name of the field that selects the union member `value` corresponds to.
    :return: `value` with `Secret` parameters replaced with a placeholder.
    """
    if typing.get_origin(model) is typing.Annotated:
        model, *metadata = typing.get_args(model)
        discriminator = _discriminator_name(metadata) or discriminator

    if isinstance(value, dict) and (
        nested_model := _discriminated_model(model, discriminator, value)
        or model_field_is_model(model, value_hint=value)
    ):
        result = {}
        for field_name, field_info in nested_model.model_fields.items():
            # Use alias if present, otherwise use field name
            key = field_info.alias if field_info.alias else field_name
            if key in value:
                result[key] = _remove_secrets_from_field(field_info, value[key])
        return result
    elif isinstance(value, list) and (nested_model := model_field_is_list_of_models(model)):
        return [remove_secrets(nested_model, v, discriminator) for v in value]
    elif isinstance(value, dict) and (nested_model := model_field_is_dict_of_models(model)):
        return {k: remove_secrets(nested_model, v) for k, v in value.items()}
    elif isinstance(value, dict) and (models := [m for m, _ in _union_models(model)]):
        # No union member validates a `value` that failed validation, which is the only reason
        # `serialize_result` falls back here. Picking one member drops the keys of all the others.
        return _remove_secrets_from_unmatched_union(models, value)
    elif typing.get_origin(model) is Secret:
        return SECRET_VALUE
    else:
        return value


def _remove_secrets_from_field(field: FieldInfo, value: typing.Any) -> typing.Any:
    """
    Remove secrets from a field value, handling discriminated unions.
    :param field: Pydantic FieldInfo object.
    :param value: field value.
    :return: value with secrets removed.
    """
    # Handle None values
    if value is None:
        return None

    # `Field(discriminator=...)` keeps the name here, `Annotated[..., Discriminator(...)]` in the metadata
    discriminator = _discriminator_name([field.discriminator, *(field.metadata or ())])
    return remove_secrets(field.annotation, value, discriminator)  # type: ignore[arg-type]


def _discriminated_model(
    model: typing.Any, discriminator: str | None, value: dict[str, typing.Any]
) -> type[BaseModel] | None:
    """
    Returns the union member whose discriminator field matches `value`, or `None`.
    :param model: potentially, a discriminated union.
    :param discriminator: discriminator name inherited from the field that declares `model`.
    :param value: dict value holding the discriminator field.
    :return: matching API model or `None`
    """
    for member, member_discriminator in _union_models(model):
        name = member_discriminator or discriminator
        if name is None or name not in value:
            continue

        field = member.model_fields_by_alias().get(name)
        if field is not None and typing.get_origin(field.annotation) is typing.Literal:
            if value[name] in typing.get_args(field.annotation):
                return member

    return None


def _remove_secrets_from_unmatched_union(
    models: list[type[BaseModel]], value: dict[str, typing.Any]
) -> dict[str, typing.Any]:
    """
    Redacts every key that any member of a union declares `Secret` and keeps the rest.
    :param models: API models the union can resolve to.
    :param value: dict value that matches none of them.
    :return: `value` with `Secret` parameters replaced with a placeholder.
    """
    result = {}
    fields_by_alias = [model.model_fields_by_alias() for model in models]
    for key, item in value.items():
        redacted = [
            _remove_secrets_from_field(field, item)
            for fields in fields_by_alias
            if (field := fields.get(key)) is not None
        ]
        if SECRET_VALUE in redacted:
            result[key] = SECRET_VALUE
        else:
            result[key] = next((r for r in redacted if r != item), item)

    return result


def _union_models(model: typing.Any) -> typing.Iterator[tuple[type[BaseModel], str | None]]:
    """
    Yields every API model `model` resolves to, looking through `Annotated` and nested unions.
    :param model: potentially, a union of API models.
    :return: an iterator of API models with the discriminator each one inherits.
    """
    discriminator = None
    if typing.get_origin(model) is typing.Annotated:
        model, *metadata = typing.get_args(model)
        discriminator = _discriminator_name(metadata)

    if isinstance(model, type) and issubclass(model, BaseModel):
        yield model, discriminator
        return

    for member in unpack_union_model_field(model):
        if member is not type(None):
            for nested, nested_discriminator in _union_models(member):
                yield nested, nested_discriminator or discriminator


def _discriminator_name(metadata: typing.Iterable[typing.Any]) -> str | None:
    """
    Returns the discriminator field name declared by any item of `metadata`, or `None`.
    :param metadata: `Annotated` metadata, or `FieldInfo` discriminator and metadata.
    :return: discriminator name or `None`
    """
    for item in metadata:
        if isinstance(item, Discriminator):
            item = item.discriminator

        if isinstance(item, str):
            return item

    return None
