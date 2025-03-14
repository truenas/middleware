from middlewared.api.base import BaseModel


class SystemGeneralKbdMapChoicesArgs(BaseModel):
    pass


class SystemGeneralKbdMapChoicesResult(BaseModel):
    result: dict[str, str]
