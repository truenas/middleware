from middlewared.api.base import BaseModel


__all__ = ["IPMIIsLoadedArgs", "IPMIIsLoadedResult",]


class IPMIIsLoadedArgs(BaseModel):
    pass


class IPMIIsLoadedResult(BaseModel):
    result: bool
    """Returns `true` if IPMI modules are loaded and available, `false` otherwise."""
