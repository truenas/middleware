from typing import Any

from pydantic import BaseModel


def model_json_schema(model: type[BaseModel], *args: Any, **kwargs: Any) -> dict[str, Any]:
    return model.model_json_schema(*args, **kwargs)
