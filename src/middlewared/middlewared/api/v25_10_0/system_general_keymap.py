from middlewared.api.base import BaseModel


__all__ = ["SystemGeneralKbdMapChoicesArgs", "SystemGeneralKbdMapChoicesResult",]


class SystemGeneralKbdMapChoicesArgs(BaseModel):
    pass


class SystemGeneralKbdMapChoicesResult(BaseModel):
    result: dict[str, str]
