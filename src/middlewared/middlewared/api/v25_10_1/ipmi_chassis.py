from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel

__all__ = ["IpmiChassisIdentifyArgs", "IpmiChassisIdentifyResult", "IpmiChassisInfoArgs", "IpmiChassisInfoResult"]


class IPMIChassisInfo(BaseModel):
    system_power: str = Field(examples=["on", "off"], description="Current system power state.")
    power_overload: str = Field(description="Power overload status indicator.")
    interlock: str = Field(description="Chassis interlock status.")
    power_fault: str = Field(description="Power fault status indicator.")
    power_control_fault: str = Field(description="Power control fault status indicator.")
    power_restore_policy: str = Field(description="Policy for restoring power after a power loss.")
    last_power_event: str = Field(description="Description of the last power-related event.")
    chassis_intrusion: str = Field(description="Chassis intrusion detection status.")
    front_panel_lockout: str = Field(description="Front panel lockout status indicator.")
    drive_fault: str = Field(description="Drive fault status indicator.")
    cooling_fan_fault: str = Field(alias="cooling/fan_fault", description="Cooling fan fault status indicator.")
    chassis_identify_state: str = Field(description="Current chassis identify LED state.")


class IpmiChassisIdentifyArgs(BaseModel):
    verb: Literal["ON", "OFF"] = Field(default="ON", description="Action to perform on the chassis identify LED.")


class IpmiChassisIdentifyResult(BaseModel):
    result: None = Field(description="Returns `null` when the chassis identify operation completes successfully.")


class IpmiChassisInfoArgs(BaseModel):
    pass


class IpmiChassisInfoResult(BaseModel):
    result: IPMIChassisInfo | dict = Field(description="IPMI chassis information or raw dictionary if parsing fails.")
