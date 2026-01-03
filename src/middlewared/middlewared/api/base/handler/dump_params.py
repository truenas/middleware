import itertools

from middlewared.api.base import BaseModel
from middlewared.api.base.model import ensure_model_ready
from middlewared.service_exception import ValidationErrors
from .accept import accept_params
from .remove_secrets import remove_secrets

__all__ = ["dump_params"]


def dump_params(model: type[BaseModel], args: list, expose_secrets: bool) -> list:
    """
    Dumps a list of `args` for a method call that accepts `model` parameters.

    :param model: `BaseModel` that defines method args.
    :param args: a list of method args.
    :param expose_secrets: if false, will replace `Secret` parameters with a placeholder.
    :return: A list of method call arguments ready to be printed.
    """
    ensure_model_ready(model)
    try:
        return accept_params(model, args, exclude_unset=True, expose_secrets=expose_secrets)
    except ValidationErrors:
        # These are invalid params, so we fall back to redacting secrets this way
        return [
            remove_secrets(field.annotation, arg) if field is not None else arg
            for field, arg in itertools.zip_longest(model.model_fields.values(), args, fillvalue=None)
        ]
