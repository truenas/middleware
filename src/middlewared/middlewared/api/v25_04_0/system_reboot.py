from middlewared.api.base import BaseModel

__all__ = ["SystemRebootInfoArgs", "RebootInfo", "SystemRebootInfoResult"]


class SystemRebootInfoArgs(BaseModel):
    pass


class RebootRequiredReason(BaseModel):
    code: str
    reason: str


class RebootInfo(BaseModel):
    boot_id: str
    reboot_required_reasons: list[RebootRequiredReason]


class SystemRebootInfoResult(BaseModel):
    result: RebootInfo
