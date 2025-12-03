from typing import Literal

from middlewared.api.base import BaseModel

from pydantic import Field


__all__ = ["IpmiChassisIdentifyArgs", "IpmiChassisIdentifyResult", "IpmiChassisInfoArgs", "IpmiChassisInfoResult"]


class IPMIChassisInfo(BaseModel):
    system_power: str = Field(examples=["on", "off"])
    """Current system power state."""
    power_overload: str
    """Power overload status indicator."""
    interlock: str
    """Chassis interlock status."""
    power_fault: str
    """Power fault status indicator."""
    power_control_fault: str
    """Power control fault status indicator."""
    power_restore_policy: str
    """Policy for restoring power after a power loss."""
    last_power_event: str
    """Description of the last power-related event."""
    chassis_intrusion: str
    """Chassis intrusion detection status."""
    front_panel_lockout: str
    """Front panel lockout status indicator."""
    drive_fault: str
    """Drive fault status indicator."""
    cooling_fan_fault: str = Field(alias="cooling/fan_fault")
    """Cooling fan fault status indicator."""
    chassis_identify_state: str
    """Current chassis identify LED state."""


class IpmiChassisIdentifyArgs(BaseModel):
    verb: Literal["ON", "OFF"] = "ON"
    """Action to perform on the chassis identify LED."""


class IpmiChassisIdentifyResult(BaseModel):
    result: None
    """Returns `null` when the chassis identify operation completes successfully."""


class IpmiChassisInfoArgs(BaseModel):
    pass


class IpmiChassisInfoResult(BaseModel):
    result: IPMIChassisInfo | dict
    """IPMI chassis information or raw dictionary if parsing fails."""
