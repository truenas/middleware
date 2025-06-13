from typing import Literal

from middlewared.api.base import BaseModel

from pydantic import Field


__all__ = ["IpmiChassisIdentifyArgs", "IpmiChassisIdentifyResult", "IpmiChassisInfoArgs", "IpmiChassisInfoResult"]


class IPMIChassisInfo(BaseModel):
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


class IpmiChassisIdentifyArgs(BaseModel):
    verb: Literal["ON", "OFF"] = "ON"


class IpmiChassisIdentifyResult(BaseModel):
    result: None


class IpmiChassisInfoArgs(BaseModel):
    pass


class IpmiChassisInfoResult(BaseModel):
    result: IPMIChassisInfo | dict
