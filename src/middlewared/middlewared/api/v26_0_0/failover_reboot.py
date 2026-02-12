# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions
from middlewared.api.base import BaseModel, NonEmptyString
from .system_reboot import RebootInfo

__all__ = ["FailoverRebootInfoArgs", "FailoverRebootInfoResult",
           "FailoverRebootOtherNodeArgs", "FailoverRebootOtherNodeResult",
           "FailoverRebootInfoChangedEvent"]


class FailoverRebootOtherNodeOptions(BaseModel):
    reason: NonEmptyString = 'System upgrade'
    """Reason for the system reboot."""
    graceful: bool = False
    """If set, call `system.reboot` to gracefully reboot the other node. By default, `failover.become_passive` will be \
    called on the other node to forcefully reboot and simulate a failover event unless there were changes in the other \
    node's boot environment."""


class FailoverRebootInfoArgs(BaseModel):
    pass


class FailoverRebootInfo(BaseModel):
    this_node: RebootInfo
    """Reboot information for the current node."""
    other_node: RebootInfo | None
    """Reboot information for the other node in the failover pair or `null` if not available."""


class FailoverRebootInfoResult(BaseModel):
    result: FailoverRebootInfo


class FailoverRebootOtherNodeArgs(BaseModel):
    options: FailoverRebootOtherNodeOptions = FailoverRebootOtherNodeOptions()
    """Options for rebooting the other node."""


class FailoverRebootOtherNodeResult(BaseModel):
    result: None
    """Returns `null` when the other node reboot is successfully initiated."""


class FailoverRebootInfoChangedEvent(BaseModel):
    id: None
    """Always null."""
    fields: FailoverRebootInfo
    """Event fields."""
