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
    """Whether this TrueNAS system is currently managed by TrueCommand."""


class TrueNASGetChassisHardwareArgs(BaseModel):
    pass


class TrueNASGetChassisHardwareResult(BaseModel):
    result: str
    """Hardware chassis model identifier for this TrueNAS system."""


class TrueNASIsIxHardwareArgs(BaseModel):
    pass


class TrueNASIsIxHardwareResult(BaseModel):
    result: bool
    """Whether this system is running on iXsystems hardware."""


class TrueNASGetEulaArgs(BaseModel):
    pass


class TrueNASGetEulaResult(BaseModel):
    result: LongString | None
    """Full text of the End User License Agreement. `null` if no EULA is required."""


class TrueNASIsEulaAcceptedArgs(BaseModel):
    pass


class TrueNASIsEulaAcceptedResult(BaseModel):
    result: bool
    """Whether the End User License Agreement has been formally accepted."""


class TrueNASAcceptEulaArgs(BaseModel):
    pass


class TrueNASAcceptEulaResult(BaseModel):
    result: None
    """Returns `null` on successful EULA acceptance."""


class TrueNASIsProductionArgs(BaseModel):
    pass


class TrueNASIsProductionResult(BaseModel):
    result: bool
    """Whether this TrueNAS system is configured for production use."""


class TrueNASSetProductionArgs(BaseModel):
    production: bool
    """Whether to configure the system for production use."""
    attach_debug: bool = False
    """Whether to attach debug information when transitioning to production mode."""


class TrueNASSetProductionResult(BaseModel):
    result: dict | None
    """Result object containing production configuration details. `null` if transition failed."""
