from typing import Literal

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
