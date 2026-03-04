from middlewared.api.base import BaseModel


__all__ = ["FailoverDisabledReasonsArgs", "FailoverDisabledReasonsResult",
           "FailoverDisabledReasonsChangedEvent"]


class FailoverDisabledReasonsArgs(BaseModel):
    pass


class FailoverDisabledReasonsResult(BaseModel):
    result: list[str]
    """Array of reasons why failover is currently disabled."""


class FailoverDisabledReasonsChangedEvent(BaseModel):
    fields: "FailoverDisabledReasonsChangedEventFields"
    """Event fields."""


class FailoverDisabledReasonsChangedEventFields(BaseModel):
    disabled_reasons: list[str]
    """Array of reasons why failover is currently disabled."""
