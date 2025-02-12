from typing import Literal

from pydantic import ConfigDict

from middlewared.api.base import BaseModel, ForUpdateMetaclass, single_argument_result

__all__ = [
    "CorePingArgs",
    "CorePingResult",
    "CoreSetOptionsArgs",
    "CoreSetOptionsResult",
    "CoreSubscribeArgs",
    "CoreSubscribeResult",
    "CoreUnsubscribeArgs",
    "CoreUnsubscribeResult",
]


class CorePingArgs(BaseModel):
    pass


class CorePingResult(BaseModel):
    result: Literal["pong"]


class CoreSetOptionsOptions(BaseModel, metaclass=ForUpdateMetaclass):
    # We can't use `extra="forbid"` here because newer version clients might try to set more options than we support
    model_config = ConfigDict(
        strict=True,
        str_max_length=1024,
        use_attribute_docstrings=True,
    )

    private_methods: bool
    py_exceptions: bool


class CoreSetOptionsArgs(BaseModel):
    options: CoreSetOptionsOptions


CoreSetOptionsResult = single_argument_result(None, "CoreSetOptionsResult")


class CoreSubscribeArgs(BaseModel):
    event: str


CoreSubscribeResult = single_argument_result(str, "CoreSubscribeResult")


class CoreUnsubscribeArgs(BaseModel):
    id_: str


CoreUnsubscribeResult = single_argument_result(None, "CoreUnsubscribeResult")
