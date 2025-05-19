from middlewared.api.base import BaseModel


__all__ = ["WebUIEnclosureDashboardArgs", "WebUIEnclosureDashboardResult",]


class WebUIEnclosureDashboardArgs(BaseModel):
    pass


class WebUIEnclosureDashboardResult(BaseModel):
    result: list[dict]
