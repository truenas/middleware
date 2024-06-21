import itertools
import typing

from middlewared.api.base import BaseModel, Private, PRIVATE_VALUE
from middlewared.service_exception import ValidationErrors
from .accept import accept_params

__all__ = ["dump_params"]


def dump_params(model, args, expose_secrets):
    try:
        return accept_params(model, args, exclude_unset=True, expose_secrets=expose_secrets)
    except ValidationErrors:
        # These are invalid params, so we fall back to redacting secrets this way
        return [
            remove_secrets(field.annotation, arg) if field is not None else arg
            for field, arg in itertools.zip_longest(model.model_fields.values(), args, fillvalue=None)
        ]


def remove_secrets(model, value):
    if isinstance(model, type) and issubclass(model, BaseModel) and isinstance(value, dict):
        return {
            k: remove_secrets(v.annotation, value[k])
            for k, v in model.model_fields.items()
            if k in value
        }
    elif typing.get_origin(model) is list and len(args := typing.get_args(model)) == 1 and isinstance(value, list):
        return [remove_secrets(args[0], v) for v in value]
    elif typing.get_origin(model) is Private:
        return PRIVATE_VALUE
    else:
        return value
