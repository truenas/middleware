from middlewared.api.base import BaseModel, ForUpdateMetaclass, single_argument_result

__all__ = ["CoreSetOptionsArgs", "CoreSetOptionsResult", "CoreSubscribeArgs", "CoreSubscribeResult",
           "CoreUnsubscribeArgs", "CoreUnsubscribeResult"]


class CoreSetOptionsOptions(BaseModel, metaclass=ForUpdateMetaclass):
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
