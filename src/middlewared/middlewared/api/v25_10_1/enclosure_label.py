from pydantic import Field

from middlewared.api.base import BaseModel

__all__ = ["EnclosureLabelSetArgs", "EnclosureLabelSetResult"]


class EnclosureLabelSetArgs(BaseModel):
    id: str = Field(description="Enclosure identifier to set the label for.")
    label: str = Field(description="New label to assign to the enclosure.")


class EnclosureLabelSetResult(BaseModel):
    result: None = Field(description="Returns `null` when the enclosure label is successfully updated.")
