from middlewared.api.base import BaseModel

__all__ = [
    'TrueNASSetProductionArgs', 'TrueNASSetProductionResult',
    'TrueNASIsProductionArgs', 'TrueNASIsProductionResult',
    'TrueNASAcceptEULAArgs', 'TrueNASAcceptEULAResult',
    'TrueNASIsEULAAcceptedArgs', 'TrueNASIsEULAAcceptedResult',
    'TrueNASGetEULAArgs', 'TrueNASGetEULAResult',
    'TrueNASIsIXHardwareArgs', 'TrueNASIsIXHardwareResult',
    'TrueNASGetChassisHardwareArgs', 'TrueNASGetChassisHardwareResult',
    'TrueNASManagedByTruecommandArgs', 'TrueNASManagedByTruecommandResult'
]

class TrueNASManagedByTruecommandArgs(BaseModel):
    pass

class TrueNASManagedByTruecommandResult(BaseModel):
    result: bool

class TrueNASGetChassisHardwareArgs(BaseModel):
    pass

class TrueNASGetChassisHardwareResult(BaseModel):
    result: str

class TrueNASIsIXHardwareArgs(BaseModel):
    pass

class TrueNASIsIXHardwareResult(BaseModel):
    result: bool

class TrueNASGetEULAArgs(BaseModel):
    pass

class TrueNASGetEULAResult(BaseModel):
    result: str

class TrueNASIsEULAAcceptedArgs(BaseModel):
    pass

class TrueNASIsEULAAcceptedResult(BaseModel):
    result: bool

class TrueNASAcceptEULAArgs(BaseModel):
    pass

class TrueNASAcceptEULAResult(BaseModel):
    result: None

class TrueNASIsProductionArgs(BaseModel):
    pass

class TrueNASIsProductionResult(BaseModel):
    result: bool

class TrueNASSetProductionArgs(BaseModel):
    production: bool
    attach_debug: bool = False

class TrueNASSetProductionResult(BaseModel):
    result: dict | None
