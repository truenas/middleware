from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, single_argument_args

__all__ = ["Enclosure2Entry", "Enclosure2SetSlotStatusArgs", "Enclosure2SetSlotStatusResult"]


class Enclosure2Entry(BaseModel):
    class Config:
        extra = "allow"


@single_argument_args("Enclosure2SetSlotStatus")
class Enclosure2SetSlotStatusArgs(BaseModel):
    enclosure_id: str = Field(description="Logical identifier of the enclosure.")
    slot: int = Field(description="Number of the drive bay whose status should change.")
    status: Literal["CLEAR", "ON", "OFF"] = Field(description="The status to set on the slot.")


class Enclosure2SetSlotStatusResult(BaseModel):
    result: None
