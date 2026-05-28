from collections.abc import Callable, Iterator
import typing

from pydantic import ValidationError

from middlewared.api.base import BaseModel
from middlewared.utils.typing_ import is_union


def model_field_is_model(
    model: typing.Any,
    value_hint: dict[str, typing.Any] | None = None,
    name_hint: str | None = None,
) -> type[BaseModel] | None:
    """
    Return` model` if it is an API model.
    Returns the first union member that is an API model if `model` is a union.
    Otherwise, returns `None`.
    :param model: potentially, API model.
    :param value_hint: value to choose the correct union member.
    :param name_hint: model name to choose the correct union member.
    :return: `model` or `None`
    """
    if isinstance(model, type) and issubclass(model, BaseModel):
        return model

    for result in matching_union_models(model, model_field_is_model):
        if value_hint is not None:
            try:
                result(**value_hint)
            except ValidationError:
                pass
            else:
                return result
        elif name_hint is not None:
            if result.__name__ == name_hint:
                return result
        else:
            return result

    return None


def model_field_is_list_of_models(model: typing.Any) -> type[BaseModel] | None:
    """
    If` model` represents a list of API models X, then it will return that model X.
    Does the same with the first matching union member if `model` is a union.
    Otherwise, returns `None`.
    :param model: potentially,  a model that represents a list of API models.
    :return: nested API model or `None`
    """
    if typing.get_origin(model) is list and len(args := typing.get_args(model)) == 1:
        return args[0]  # type: ignore[no-any-return]

    return first_matching_union_model(model, model_field_is_list_of_models)


def model_field_is_dict_of_models(model: typing.Any) -> type[BaseModel] | None:
    """
    If `model` represents a dict of API models (dict[str, X]), then it will return that model X.
    Does the same with the first matching union member if `model` is a union.
    Otherwise, returns `None`.
    :param model: potentially, a model that represents a dict of API models.
    :return: nested API model or `None`
    """
    if typing.get_origin(model) is dict and len(args := typing.get_args(model)) == 2:
        # Return value type, not key type
        return args[1]  # type: ignore[no-any-return]

    return first_matching_union_model(model, model_field_is_dict_of_models)


def unpack_union_model_field(model: typing.Any) -> typing.Generator[typing.Any, None, None]:
    # Handle both typing.Union and types.UnionType (|)
    origin = typing.get_origin(model)
    if is_union(origin):
        for member in typing.get_args(model):
            yield member

_UnionMatches = Callable[[typing.Any], type[BaseModel] | None]


def matching_union_models(model: typing.Any, func: _UnionMatches) -> Iterator[type[BaseModel]]:
    for member in unpack_union_model_field(model):
        if member is type(None):
            continue

        if result := func(member):
            yield result


def first_matching_union_model(model: typing.Any, func: _UnionMatches) -> type[BaseModel] | None:
    for result in matching_union_models(model, func):
        return result

    return None
