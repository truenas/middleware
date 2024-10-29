from middlewared.api.base import (
    BaseModel,
    NonEmptyString,
    single_argument_args,
)
from middlewared.utils.directoryservices.krb5_constants import (
    krb5ccache,
)
from pydantic import Field, Secret
from typing import Literal


__all__ = [
    'ActivedirectoryLeaveArgs', 'ActivedirectoryLeaveResult',
]


class ActivedirectoryUsernamePassword(BaseModel):
    username: NonEmptyString
    password: Secret[NonEmptyString]


class ActivedirectoryLeaveArgs(BaseModel):
    ad_cred: ActivedirectoryUsernamePassword


class ActivedirectoryLeaveResult(BaseModel):
    result: Literal[True]
