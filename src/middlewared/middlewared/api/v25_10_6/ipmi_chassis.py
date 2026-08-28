from typing import Literal

from middlewared.api.base import BaseModel

from pydantic import Field


__all__ = [
    "IpmiChassisIdentifyArgs", "IpmiChassisIdentifyResult",
    "IpmiChassisInfoArgs", "IpmiChassisInfoResult"
]


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


class IpmiChassisIdentifyRequest(BaseModel):
    verb: Literal["ON", "OFF"] = Field(default="ON", description="Action to perform on the chassis identify LED.")
    apply_remote: bool = Field(
        default=False,
        description=(
            "If on an HA system, and this field is set to True, the settings will be sent to the remote controller."
        ),
    )


class IpmiChassisIdentifyArgs(BaseModel):
    data: IpmiChassisIdentifyRequest = Field(
        default_factory=IpmiChassisIdentifyRequest,
        description="Request parameters for IPMI chassis identify operation.",
    )


class IpmiChassisIdentifyResult(BaseModel):
    result: None = Field(description="Returns `null` when the chassis identify operation completes successfully.")


class IpmiChassisInfoRequest(BaseModel):
    query_remote: bool = Field(
        alias='query-remote',
        default=False,
        description="Whether to query remote IPMI chassis information on HA systems.",
    )


class IpmiChassisInfoArgs(BaseModel):
    data: IpmiChassisInfoRequest = Field(
        default_factory=IpmiChassisInfoRequest,
        description="Request parameters for IPMI chassis information.",
    )


class IpmiChassisInfoResult(BaseModel):
    result: IPMIChassisInfo | dict = Field(description="IPMI chassis information or raw dictionary if parsing fails.")
