from middlewared.api.base import BaseModel


class WebUIEnclosureDashboardArgs(BaseModel):
    pass


class WebUIEnclosureDashboardResult(BaseModel):
    result: list[dict] | list
