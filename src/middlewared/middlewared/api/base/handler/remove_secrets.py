import types
import typing

from pydantic import Discriminator, Secret

from middlewared.api.base import BaseModel, SECRET_VALUE
from middlewared.utils.typing_ import is_union
from .inspect import model_field_is_model, model_field_is_list_of_models, model_field_is_dict_of_models

__all__ = ["remove_secrets"]


def remove_secrets(model: type[BaseModel], value):
    """
    Removes `Secret` values from a model value.
    :param model: `BaseModel` that corresponds to `value`.
    :param value: value that potentially contains `Secret` data.
    :return: `value` with `Secret` parameters replaced with a placeholder.
    """
    if isinstance(value, dict) and (nested_model := model_field_is_model(model, value_hint=value)):
        result = {}
        for field_name, field_info in nested_model.model_fields.items():
            # Use alias if present, otherwise use field name
            key = field_info.alias if field_info.alias else field_name
            if key in value:
                result[key] = _remove_secrets_from_field(field_info, value[key])
        return result
    elif isinstance(value, list) and (nested_model := model_field_is_list_of_models(model)):
        return [remove_secrets(nested_model, v) for v in value]
    elif isinstance(value, dict) and (nested_model := model_field_is_dict_of_models(model)):
        return {k: remove_secrets(nested_model, v) for k, v in value.items()}
    elif typing.get_origin(model) is Secret:
        return SECRET_VALUE
    else:
        return value


def _remove_secrets_from_field(field, value):
    """
    Remove secrets from a field value, handling discriminated unions.
    :param field: Pydantic FieldInfo object.
    :param value: field value.
    :return: value with secrets removed.
    """
    # Handle None values
    if value is None:
        return None

    # Check if this field has a discriminator (discriminated union)
    if isinstance(value, dict) and (discriminated_model := _get_discriminated_union_model_from_field(field, value)):
        return remove_secrets(discriminated_model, value)
    else:
        return remove_secrets(field.annotation, value)


def _get_discriminated_union_model_from_field(field, value: dict) -> type[BaseModel] | None:
    """
    If `field` is a discriminated union field, returns the appropriate union member
    based on the discriminator field value in `value`.
    :param field: Pydantic FieldInfo that may contain a discriminated union.
    :param value: dict value containing the discriminator field.
    :return: the matching BaseModel from the union, or None.
    """
    annotation = field.annotation
    origin = typing.get_origin(annotation)

    # The annotation can be:
    # 1. Annotated[Union[...], Discriminator(...)] - metadata directly on field
    # 2. Union[Annotated[Union[...], Discriminator(...)], None] - Optional of annotated union
    # 3. Union[Model1, Model2] - just a union without discriminator

    # First, check if field has metadata with a Discriminator
    discriminator = None
    if hasattr(field, 'metadata') and field.metadata:
        for meta in field.metadata:
            if isinstance(meta, Discriminator):
                discriminator = meta
                break

    # If no discriminator found and this is a Union, check if any member is an Annotated type with Discriminator
    if not discriminator and (origin is types.UnionType or origin is typing.Union):
        for member in typing.get_args(annotation):
            if typing.get_origin(member) is typing.Annotated:
                # Check metadata of the Annotated member
                annotated_args = typing.get_args(member)
                if len(annotated_args) > 1:
                    for meta in annotated_args[1:]:
                        if isinstance(meta, Discriminator):
                            discriminator = meta
                            # Use the inner union as the annotation
                            annotation = annotated_args[0]
                            break
                if discriminator:
                    break

    if not discriminator:
        return None

    # Now annotation should be the Union[Model1, Model2, ...]
    origin = typing.get_origin(annotation)
    if not is_union(origin):
        return None

    # Get all union members
    union_members = typing.get_args(annotation)

    # Filter out None type and find BaseModel members
    model_members = [m for m in union_members if isinstance(m, type) and issubclass(m, BaseModel)]

    if not model_members:
        return None

    # Get the discriminator field value from the data
    discriminator_field = discriminator.discriminator
    if not isinstance(discriminator_field, str) or discriminator_field not in value:
        return None

    discriminator_value = value[discriminator_field]

    # Find the matching union member
    for member in model_members:
        # Check if this member matches the discriminator value
        if discriminator_field in member.model_fields:
            member_field = member.model_fields[discriminator_field]
            # Check if the field annotation is a Literal that matches our value
            field_origin = typing.get_origin(member_field.annotation)
            if field_origin is typing.Literal:
                literal_values = typing.get_args(member_field.annotation)
                if discriminator_value in literal_values:
                    return member

    return None
