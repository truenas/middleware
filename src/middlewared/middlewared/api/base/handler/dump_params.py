import itertools
import typing

from pydantic import Secret

from middlewared.api.base import BaseModel, SECRET_VALUE
from middlewared.service_exception import ValidationErrors
from .accept import accept_params
from .inspect import model_field_is_model, model_field_is_list_of_models

__all__ = ["dump_params"]


def dump_params(model: type[BaseModel], args: list, expose_secrets: bool) -> list:
    """
    Dumps a list of `args` for a method call that accepts `model` parameters.

    :param model: `BaseModel` that defines method args.
    :param args: a list of method args.
    :param expose_secrets: if false, will replace `Private` parameters with a placeholder.
    :return: A list of method call arguments ready to be printed.
    """
    try:
        return accept_params(model, args, exclude_unset=True, expose_secrets=expose_secrets)
    except ValidationErrors:
        # These are invalid params, so we fall back to redacting secrets this way
        return [
            remove_secrets(field.annotation, arg) if field is not None else arg
            for field, arg in itertools.zip_longest(model.model_fields.values(), args, fillvalue=None)
        ]


def remove_secrets(model: type[BaseModel], value):
    """
    Removes `Private` values from a model value.
    :param model: `BaseModel` that corresponds to `value`.
    :param value: value that potentially contains `Private` data.
    :return: `value` with `Private` parameters replaced with a placeholder.
    """
    if isinstance(value, dict) and (nested_model := model_field_is_model(model)):
        return {
            k: remove_secrets(v.annotation, value[k])
            for k, v in nested_model.model_fields.items()
            if k in value
        }
    elif isinstance(value, list) and (nested_model := model_field_is_list_of_models(model)):
        return [remove_secrets(nested_model, v) for v in value]
    elif typing.get_origin(model) is Secret:
        return SECRET_VALUE
    else:
        return value
