from middlewared.api.base import BaseModel
from middlewared.api.current import Alert


class DiskTemperatureAlertsArgs(BaseModel):
    names: list[str]


class DiskTemperatureAlertsResult(BaseModel):
    result: list[Alert]
