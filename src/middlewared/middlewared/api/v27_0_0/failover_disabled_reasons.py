from pydantic import Field

from middlewared.api.base import BaseModel


__all__ = ["FailoverDisabledReasonsArgs", "FailoverDisabledReasonsResult",
           "FailoverDisabledReasonsChangedEvent"]


class FailoverDisabledReasonsArgs(BaseModel):
    pass


class FailoverDisabledReasonsResult(BaseModel):
    result: list[str] = Field(description="Array of reasons why failover is currently disabled.")


class FailoverDisabledReasonsChangedEvent(BaseModel):
    fields: "FailoverDisabledReasonsChangedEventFields" = Field(description="Event fields.")


class FailoverDisabledReasonsChangedEventFields(BaseModel):
    disabled_reasons: list[str] = Field(description="Array of reasons why failover is currently disabled.")
