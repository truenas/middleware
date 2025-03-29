from middlewared.api.base import BaseModel

__all__ = ("SystemAdvancedGpuArgs", "SystemAdvancedGpuResult")


class SystemAdvancedGpuArgs(BaseModel):
    pass


class SystemAdvancedGpuResult(BaseModel):
    result: dict


class SystemAdvancedUpdateGpuPciIdArgs(BaseModel):
    data: list[str]


class SystemAdvancedUpdateGpuPciIdResult(BaseModel):
    result: None
