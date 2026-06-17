import dataclasses
import logging
import typing

from pydantic import ValidationError

from middlewared.api.base import BaseModel
from middlewared.service_exception import ValidationErrors

from .remove_secrets import remove_secrets

logger = logging.getLogger(__name__)

__all__ = ["serialize_result", "serialize_dataclasses"]


def serialize_dataclasses(result: typing.Any) -> typing.Any:
    """Recursively convert dataclass instances within a method result into plain dicts.

    This is the dataclass analogue of `serialize_result`: it is used for methods that return
    dataclasses without a `BaseModel` return type (e.g. private methods consumed in-process but
    still reachable over the wire), so the result can be JSON-serialized for transport.
    """
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        return dataclasses.asdict(result)
    if isinstance(result, list):
        return [serialize_dataclasses(item) for item in result]
    if isinstance(result, tuple):
        return tuple(serialize_dataclasses(item) for item in result)
    if isinstance(result, dict):
        return {key: serialize_dataclasses(value) for key, value in result.items()}
    return result


def serialize_result(
    model: type[BaseModel],
    result: typing.Any,
    expose_secrets: bool,
    allow_fallback: bool,
) -> typing.Any:
    """
    Serializes a `result` of the method execution using the corresponding `model`.

    :param model: `BaseModel` that defines method return value.
    :param result: method return value.
    :param expose_secrets: if false, will replace `Secret` parameters with a placeholder.
    :param allow_fallback: if false, a serialization error will raise an exception.
    :return: serialized method execution result.
    """
    try:
        return model(result=result).model_dump(
            context={"expose_secrets": expose_secrets},
            warnings=False,
            by_alias=True,
        )["result"]
    except (ValidationError, ValidationErrors) as e:
        if not allow_fallback:
            raise

        logger.warning(f"Serialization error when serializing {model}: {e}. Falling back to `remove_secrets`")
        if expose_secrets:
            return result
        else:
            return remove_secrets(model, result)
