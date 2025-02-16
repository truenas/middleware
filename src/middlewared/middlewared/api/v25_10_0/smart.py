from typing import Literal

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, single_argument_args

__all__ = ["SmartEntry", "SmartUpdateArgs", "SmartUpdateResult"]


class SmartEntry(BaseModel):
    id: int
    interval: int
    "an integer value in minutes which defines how often smartd activates to check if any tests are configured to run."
    powermode: Literal["NEVER", "SLEEP", "STANDBY", "IDLE"]
    difference: int
    """integer values on which alerts for SMART are configured if the disks temperature crosses the assigned threshold
    for each respective attribute. They default to 0 which indicates they are disabled."""
    informational: int
    critical: int


@single_argument_args("smart_update")
class SmartUpdateArgs(SmartEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class SmartUpdateResult(BaseModel):
    result: SmartEntry
