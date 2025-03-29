from middlewared.api.base import BaseModel

__all__ = (
    "SystemAdvancedGpuChoicesArgs",
    "SystemAdvancedGpuChoicesResult",
    "SystemAdvancedUpdateGpuPciIdArgs",
    "SystemAdvancedUpdateGpuPciIdResult",
)


class SystemAdvancedGpuChoicesArgs(BaseModel):
    pass


class SystemAdvancedGpuChoicesResult(BaseModel):
    result: dict


class SystemAdvancedUpdateGpuPciIdArgs(BaseModel):
    data: list[str]


class SystemAdvancedUpdateGpuPciIdResult(BaseModel):
    result: None
