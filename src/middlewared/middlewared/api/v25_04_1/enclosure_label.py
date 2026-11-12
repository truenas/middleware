from middlewared.api.base import BaseModel, Multiline

__all__ = ["EnclosureLabelSetArgs", "EnclosureLabelSetResult"]


class EnclosureLabelSetArgs(BaseModel):
    id: str
    label: Multiline[str]


class EnclosureLabelSetResult(BaseModel):
    result: None
