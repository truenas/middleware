from middlewared.api.base import BaseModel

__all__ = ["EnclosureLabelSetArgs", "EnclosureLabelUpdateResult"]


class EnclosureLabelSetArgs(BaseModel):
    id: str
    label: str


class EnclosureLabelUpdateResult(BaseModel):
    result: None
