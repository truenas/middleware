from pydantic import BaseModel, ConfigDict

__all__ = ["EmptyDict"]


class EmptyDict(BaseModel):
    model_config = ConfigDict(extra="forbid")
