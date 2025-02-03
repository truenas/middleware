from middlewared.api.base import BaseModel


class FCCapableArgs(BaseModel):
    pass


class FCCapableResult(BaseModel):
    result: bool
