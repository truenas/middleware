from middlewared.api.base import BaseModel, ForUpdateMetaclass

__all__ = ["EnclosureLabelUpdateData", "EnclosureLabelUpdateArgs", "EnclosureLabelUpdateResult"]


class EnclosureLabelUpdateData(BaseModel, metaclass=ForUpdateMetaclass):
    label: str


class EnclosureLabelUpdateArgs(BaseModel):
    id: str
    enclosure_update: EnclosureLabelUpdateData


class EnclosureLabelUpdateResult(BaseModel):
    result: None
