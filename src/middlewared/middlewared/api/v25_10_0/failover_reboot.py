# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions
from middlewared.api.base import BaseModel, single_argument_result
from .system_reboot import RebootInfo

__all__ = ["FailoverRebootInfoArgs", "FailoverRebootInfoResult",
           "FailoverRebootOtherNodeArgs", "FailoverRebootOtherNodeResult"]


class FailoverRebootInfoArgs(BaseModel):
    pass


@single_argument_result
class FailoverRebootInfoResult(BaseModel):
    this_node: RebootInfo
    """Reboot information for the current node."""
    other_node: RebootInfo | None
    """Reboot information for the other node in the failover pair or `null` if not available."""


class FailoverRebootOtherNodeArgs(BaseModel):
    pass


class FailoverRebootOtherNodeResult(BaseModel):
    result: None
    """Returns `null` when the other node reboot is successfully initiated."""
