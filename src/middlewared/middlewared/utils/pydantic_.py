from typing import Any

from pydantic import BaseModel, Secret
from pydantic.json_schema import GenerateJsonSchema


class _GenerateJsonSchema(GenerateJsonSchema):
    def encode_default(self, dft: Any) -> Any:
        # `BaseModel` wraps a `Secret` field's default in a `Secret`, which encodes as its redacted display
        # (`""` for a falsy value, `"**********"` otherwise) and contradicts the field's type, e.g. a boolean field
        # documented with a string default. A default is a constant in the code rather than a user's secret, so
        # document the value itself.
        if isinstance(dft, Secret):
            dft = dft.get_secret_value()

        return super().encode_default(dft)


def model_json_schema(model: type[BaseModel], *args: Any, **kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("schema_generator", _GenerateJsonSchema)
    return model.model_json_schema(*args, **kwargs)
