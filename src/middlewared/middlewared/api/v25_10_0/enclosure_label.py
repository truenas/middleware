from middlewared.api.base import BaseModel

__all__ = ["EnclosureLabelSetArgs", "EnclosureLabelSetResult"]


class EnclosureLabelSetArgs(BaseModel):
    id: str
    label: str


class EnclosureLabelSetResult(BaseModel):
    result: None
