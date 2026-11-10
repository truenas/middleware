from pydantic import Field, Secret

from middlewared.api.base import BaseModel
from middlewared.utils.pydantic_ import model_json_schema


class SecretDefaults(BaseModel):
    flag: Secret[bool] = Field(default=Secret(False))
    count: Secret[int] = Field(default=Secret(10000))
    text: Secret[str] = Field(default=Secret(""))


def test_secret_default_documents_its_value_in_json_schema():
    """The JSON schema documents a wrapped default as its value, not its redacted display."""
    properties = model_json_schema(SecretDefaults)["properties"]
    assert properties["flag"]["default"] is False
    assert properties["count"]["default"] == 10000
    assert properties["text"]["default"] == ""
