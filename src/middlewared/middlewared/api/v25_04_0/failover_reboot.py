# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions
from middlewared.api.base import BaseModel, single_argument_result

__all__ = ["FailoverRebootRequiredArgs", "FailoverRebootRequiredResult"]


class FailoverRebootRequiredArgs(BaseModel):
    pass


class FailoverRebootRequiredResultThisNode(BaseModel):
    id: str
    reboot_required: bool
    reboot_required_reasons: list[str]


class FailoverRebootRequiredResultOtherNode(FailoverRebootRequiredResultThisNode):
    id: str | None
    reboot_required: bool | None


@single_argument_result
class FailoverRebootRequiredResult(BaseModel):
    this_node: FailoverRebootRequiredResultThisNode
    other_node: FailoverRebootRequiredResultOtherNode
