import types
import typing

from pydantic import ValidationError

from middlewared.api.base import BaseModel


def model_field_is_model(model, value_hint=None, name_hint=None) -> type[BaseModel] | None:
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
    # Handle both typing.Union and types.UnionType (|)
    origin = typing.get_origin(model)
    if origin is types.UnionType or origin is typing.Union:
        for member in typing.get_args(model):
            # Skip None type in Optional/Union
            if member is type(None):
                continue
            if result := model_field_is_model(member):
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


def model_field_is_list_of_models(model) -> type[BaseModel] | None:
    """
    If` model` represents a list of API models X, then it will return that model X.
    Does the same with the first matching union member if `model` is a union.
    Otherwise, returns `None`.
    :param model: potentially,  a model that represents a list of API models.
    :return: nested API model or `None`
    """
    if typing.get_origin(model) is list and len(args := typing.get_args(model)) == 1:
        return args[0]
    # Handle both typing.Union and types.UnionType (|)
    origin = typing.get_origin(model)
    if origin is types.UnionType or origin is typing.Union:
        for member in typing.get_args(model):
            if member is type(None):
                continue
            if result := model_field_is_list_of_models(member):
                return result


def model_field_is_dict_of_models(model) -> type[BaseModel] | None:
    """
    If `model` represents a dict of API models (dict[str, X]), then it will return that model X.
    Does the same with the first matching union member if `model` is a union.
    Otherwise, returns `None`.
    :param model: potentially, a model that represents a dict of API models.
    :return: nested API model or `None`
    """
    if typing.get_origin(model) is dict and len(args := typing.get_args(model)) == 2:
        return args[1]  # Return value type, not key type
    # Handle both typing.Union and types.UnionType (|)
    origin = typing.get_origin(model)
    if origin is types.UnionType or origin is typing.Union:
        for member in typing.get_args(model):
            if member is type(None):
                continue
            if result := model_field_is_dict_of_models(member):
                return result
