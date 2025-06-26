from middlewared.api.base import BaseModel, LongString


__all__ = [
    'TrueNASSetProductionArgs', 'TrueNASSetProductionResult',
    'TrueNASIsProductionArgs', 'TrueNASIsProductionResult',
    'TrueNASAcceptEulaArgs', 'TrueNASAcceptEulaResult',
    'TrueNASIsEulaAcceptedArgs', 'TrueNASIsEulaAcceptedResult',
    'TrueNASGetEulaArgs', 'TrueNASGetEulaResult',
    'TrueNASIsIxHardwareArgs', 'TrueNASIsIxHardwareResult',
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


class TrueNASIsIxHardwareArgs(BaseModel):
    pass


class TrueNASIsIxHardwareResult(BaseModel):
    result: bool


class TrueNASGetEulaArgs(BaseModel):
    pass


class TrueNASGetEulaResult(BaseModel):
    result: LongString | None


class TrueNASIsEulaAcceptedArgs(BaseModel):
    pass


class TrueNASIsEulaAcceptedResult(BaseModel):
    result: bool


class TrueNASAcceptEulaArgs(BaseModel):
    pass


class TrueNASAcceptEulaResult(BaseModel):
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
