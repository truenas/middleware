from middlewared.api.base import BaseModel

__all__ = ["EnclosureLabelSetArgs", "EnclosureLabelSetResult"]


class EnclosureLabelSetArgs(BaseModel):
    id: str
    """Enclosure identifier to set the label for."""
    label: str
    """New label to assign to the enclosure."""


class EnclosureLabelSetResult(BaseModel):
    result: None
    """Returns `null` when the enclosure label is successfully updated."""
