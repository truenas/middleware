from typing import Literal

from middlewared.api.base import BaseModel, ForUpdateMetaclass

from pydantic import Field


class ChassisInfoEntry(BaseModel):
    system_power: str
    power_overload: str
    interlock: str
    power_fault: str
    power_control_fault: str
    power_restore_policy: str
    last_power_event: str
    chassis_intrusion: str
    front_panel_lockout: str
    drive_fault: str
    cooling_fan_fault: str = Field(alias="cooling/fan_fault")
    chassis_identify_state: str


class ChassisIdentifyArgs(BaseModel):
    verb: Literal["ON", "OFF"]


class ChassisIdentifyResult(BaseModel):
    pass


class ChassisInfoArgs(BaseModel):
    pass


class ChassisInfoResult(ChassisInfoEntry, metaclass=ForUpdateMetaclass):
    pass
