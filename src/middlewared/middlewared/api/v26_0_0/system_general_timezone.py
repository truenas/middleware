from middlewared.api.base import BaseModel


__all__ = ["SystemGeneralTimezoneChoicesArgs", "SystemGeneralTimezoneChoicesResult", "SystemGeneralTimezoneChoices"]


class SystemGeneralTimezoneChoicesArgs(BaseModel):
    pass


SystemGeneralTimezoneChoices = dict[str, str]


class SystemGeneralTimezoneChoicesResult(BaseModel):
    result: SystemGeneralTimezoneChoices
    """Object of available timezone identifiers and their descriptive names."""
