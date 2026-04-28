from typing import Any, Literal

from pydantic import BaseModel

from middlewared.api.base.handler.inspect import (
    model_field_is_dict_of_models,
    model_field_is_list_of_models,
    model_field_is_model,
)

MockReturnModel = tuple[Literal['model', 'list', 'dict'], type[BaseModel]]


def coerce_mock_result(result: Any, mock_return_model: MockReturnModel | None) -> Any:
    """Convert dict mock results to Pydantic models for generic services."""
    if mock_return_model is None:
        return result

    kind, entry_type = mock_return_model

    if kind == 'model' and isinstance(result, dict):
        return entry_type.model_construct(**result)

    if kind == 'list' and isinstance(result, list):
        return [
            entry_type.model_construct(**item) if isinstance(item, dict) else item
            for item in result
        ]

    if kind == 'dict' and isinstance(result, dict):
        return {
            k: entry_type.model_construct(**v) if isinstance(v, dict) else v
            for k, v in result.items()
        }

    return result


def get_mock_return_model(serviceobj: Any, methodobj: Any) -> MockReturnModel | None:
    """Get the Pydantic model for auto-wrapping mock return values.

    Only applies to generic services (``_config.generic = True``) where
    methods return Pydantic model instances at runtime.
    """
    config = getattr(serviceobj, '_config', None)
    if not getattr(config, 'generic', False):
        return None

    if not hasattr(methodobj, 'new_style_returns'):
        return None

    try:
        annotation = methodobj.new_style_returns.model_fields['result'].annotation
    except (AttributeError, KeyError):
        return None

    if model := model_field_is_model(annotation):
        return ('model', model)

    if (
        (model := model_field_is_list_of_models(annotation))
        and isinstance(model, type) and issubclass(model, BaseModel)
    ):
        return ('list', model)

    if (
        (model := model_field_is_dict_of_models(annotation))
        and isinstance(model, type) and issubclass(model, BaseModel)
    ):
        return ('dict', model)

    return None
