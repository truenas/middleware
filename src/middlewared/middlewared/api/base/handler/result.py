import logging

from middlewared.api.base import BaseModel
from middlewared.service_exception import ValidationErrors
from .remove_secrets import remove_secrets

logger = logging.getLogger(__name__)

__all__ = ["serialize_result"]


def serialize_result(model: type[BaseModel], result, expose_secrets: bool, allow_fallback: bool):
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
    except ValidationErrors as e:
        if not allow_fallback:
            raise

        logger.warning(f"Serialization error when serializing {model}: {e}. Falling back to `remove_secrets`")
        if expose_secrets:
            return result
        else:
            return remove_secrets(model, result)
