from middlewared.api.base import BaseModel, single_argument_result

__all__ = ["SystemRebootInfoArgs", "SystemRebootInfoResult"]


class SystemRebootInfoArgs(BaseModel):
    pass


class RebootRequiredReason(BaseModel):
    code: str
    reason: str


@single_argument_result
class SystemRebootInfoResult(BaseModel):
    boot_id: str
    reboot_required_reasons: list[RebootRequiredReason]
