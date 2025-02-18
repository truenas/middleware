from typing import Literal

from middlewared.api.base import BaseModel, single_argument_args


__all__ = ["Enclosure2Entry", "Enclosure2SetSlotStatusArgs", "Enclosure2SetSlotStatusResult"]


class Enclosure2Entry(BaseModel):
    class Config:
        extra = "allow"


@single_argument_args("Enclosure2SetSlotStatus")
class Enclosure2SetSlotStatusArgs(BaseModel):
    enclosure_id: str
    slot: int
    status: Literal["CLEAR", "ON", "OFF"]


class Enclosure2SetSlotStatusResult(BaseModel):
    result: None
