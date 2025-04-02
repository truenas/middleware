from middlewared.api.base import BaseModel


class IPMIIsLoadedArgs(BaseModel):
    pass


class IPMIIsLoadedResult(BaseModel):
    result: bool
