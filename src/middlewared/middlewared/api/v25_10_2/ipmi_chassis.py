from typing import Literal

from middlewared.api.base import BaseModel

from pydantic import Field


__all__ = [
    "IpmiChassisIdentifyArgs", "IpmiChassisIdentifyResult",
    "IpmiChassisInfoArgs", "IpmiChassisInfoResult"
]


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


class IpmiChassisIdentifyRequest(BaseModel):
    verb: Literal["ON", "OFF"] = "ON"
    """Action to perform on the chassis identify LED."""
    apply_remote: bool = False
    """If on an HA system, and this field is set to True, the settings will be sent to the remote controller."""


class IpmiChassisIdentifyArgs(BaseModel):
    data: IpmiChassisIdentifyRequest = Field(default_factory=IpmiChassisIdentifyRequest)
    """Request parameters for IPMI chassis identify operation."""

    @classmethod
    def from_previous(cls, previous_value):
        """Convert from v25_10_1 format (flat verb field) to v25_10_2 format (wrapped in data)."""
        # Previous version: {'verb': 'ON'}
        # New version: {'data': {'verb': 'ON', 'apply_remote': False}}
        return cls(data=previous_value)

    @classmethod
    def to_previous(cls, value):
        """Convert from v25_10_2 format (wrapped in data) to v25_10_1 format (flat verb field)."""
        # Return only the verb field, drop apply_remote since it didn't exist in previous version
        return {'verb': value['data']['verb']}


class IpmiChassisIdentifyResult(BaseModel):
    result: None
    """Returns `null` when the chassis identify operation completes successfully."""


class IpmiChassisInfoRequest(BaseModel):
    query_remote: bool = Field(alias='query-remote', default=False)
    """Whether to query remote IPMI chassis information on HA systems."""


class IpmiChassisInfoArgs(BaseModel):
    data: IpmiChassisInfoRequest = Field(default_factory=IpmiChassisInfoRequest)
    """Request parameters for IPMI chassis information."""

    @classmethod
    def from_previous(cls, previous_value):
        """Convert from v25_10_1 format (empty) to v25_10_2 format (wrapped in data)."""
        # Previous version: {} (no parameters)
        # New version: {'data': {'query_remote': False}}
        # If previous_value is empty dict or None, use defaults
        if not previous_value:
            return cls()
        # Otherwise wrap it in data
        return cls(data=previous_value)

    @classmethod
    def to_previous(cls, value):
        """Convert from v25_10_2 format (wrapped in data) to v25_10_1 format (empty)."""
        # Previous version had no parameters, so return empty dict
        return {}


class IpmiChassisInfoResult(BaseModel):
    result: IPMIChassisInfo | dict
    """IPMI chassis information or raw dictionary if parsing fails."""
