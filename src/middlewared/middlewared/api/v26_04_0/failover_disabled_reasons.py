from middlewared.api.base import BaseModel


__all__ = ["FailoverDisabledReasonsReasonsArgs", "FailoverDisabledReasonsReasonsResult"]


class FailoverDisabledReasonsReasonsArgs(BaseModel):
    pass


class FailoverDisabledReasonsReasonsResult(BaseModel):
    result: list[str]
    """Array of reasons why failover is currently disabled."""
