from pydantic import Field

from middlewared.api.base import BaseModel


__all__ = ["FailoverDisabledReasonsArgs", "FailoverDisabledReasonsResult"]


class FailoverDisabledReasonsArgs(BaseModel):
    pass


class FailoverDisabledReasonsResult(BaseModel):
    result: list[str] = Field(description="Array of reasons why failover is currently disabled.")
