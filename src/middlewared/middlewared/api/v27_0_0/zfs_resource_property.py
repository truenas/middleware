from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel

__all__: tuple[str, ...] = ()

PROP_SRC = Literal["NONE", "DEFAULT", "TEMPORARY", "LOCAL", "INHERITED", "RECEIVED"]


class SourceValue(BaseModel):
    type: PROP_SRC = Field(description="The source type.")
    value: str | None = Field(description="The source value.")


class PropertyValue(BaseModel):
    raw: str = Field(description="The raw value of the property.")
    source: SourceValue | None = Field(description="The source from where this property received its value.")
    value: int | float | str | bool | None = Field(description="The parsed raw value of the property.")
