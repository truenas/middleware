from middlewared.api.base import BaseModel


__all__ = ["FailoverDisabledReasonsReasonsArgs", "FailoverDisabledReasonsReasonsResult",
           "FailoverDisabledReasonsChangedEvent"]


class FailoverDisabledReasonsReasonsArgs(BaseModel):
    pass


class FailoverDisabledReasonsReasonsResult(BaseModel):
    result: list[str]
    """Array of reasons why failover is currently disabled."""


class FailoverDisabledReasonsChangedEvent(BaseModel):
    fields: "FailoverDisabledReasonsChangedEventFields"
    """Event fields."""


class FailoverDisabledReasonsChangedEventFields(BaseModel):
    disabled_reasons: list[str]
    """Array of reasons why failover is currently disabled."""
