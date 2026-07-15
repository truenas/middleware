from pydantic import Field

from middlewared.api.base import BaseModel

__all__ = ["WebUIEnclosureDashboardArgs", "WebUIEnclosureDashboardResult",]


class WebUIEnclosureDashboardArgs(BaseModel):
    pass


class WebUIEnclosureDashboardResult(BaseModel):
    result: list[dict] = Field(description="Array of enclosure information objects for the web UI dashboard display.")
