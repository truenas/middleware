from middlewared.api.base import BaseModel


__all__ = ["FailoverDisabledReasonsArgs", "FailoverDisabledReasonsResult"]


class FailoverDisabledReasonsArgs(BaseModel):
    pass


class FailoverDisabledReasonsResult(BaseModel):
    result: list[str]
