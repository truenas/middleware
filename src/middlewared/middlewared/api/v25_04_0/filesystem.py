from middlewared.api.base import (
    BaseModel,
    NonEmptyString,
    UnixPerm,
    single_argument_args,
)
from pydantic import Field, model_validator
from typing import Literal, Self
from middlewared.utils.filesystem.acl import (
    ACL_UNDEFINED_ID,
)
from .acl import AceWhoId

__all__ = [
    'FilesystemChownArgs', 'FilesystemChownResult',
    'FilesystemSetPermArgs', 'FilesystemSetPermResult',
]


UNSET_ENTRY = frozenset([ACL_UNDEFINED_ID, None])


class FilesystemRecursionOptions(BaseModel):
    recursive: bool = False
    traverse: bool = False
    "If set do not limit to single dataset / filesystem."


class FilesystemChownOptions(FilesystemRecursionOptions):
    pass


class FilesystemSetpermOptions(FilesystemRecursionOptions):
    stripacl: bool = False


class FilesystemPermChownBase(BaseModel):
    path: NonEmptyString
    uid: AceWhoId | None = None
    user: NonEmptyString | None = None
    gid: AceWhoId | None = None
    group: NonEmptyString | None = None


@single_argument_args('filesystem_chown')
class FilesystemChownArgs(FilesystemPermChownBase):
    options: FilesystemChownOptions = Field(default=FilesystemChownOptions())

    @model_validator(mode='after')
    def user_group_present(self) -> Self:
        if all(field in UNSET_ENTRY for field in (self.uid, self.user, self.gid, self.group)):
            raise ValueError(
                'At least one of uid, gid, user, and group must be set in chown payload'
            )

        return self


class FilesystemChownResult(BaseModel):
    result: Literal[None]


@single_argument_args('filesystem_setperm')
class FilesystemSetPermArgs(FilesystemPermChownBase):
    mode: UnixPerm | None = None
    options: FilesystemSetpermOptions = Field(default=FilesystemSetpermOptions())

    @model_validator(mode='after')
    def payload_is_actionable(self) -> Self:
        """ User should be changing something. Either stripping ACL or setting mode """
        if self.mode is None and self.options.stripacl is False:
            raise ValueError(
                'Payload must either explicitly specify permissions or '
                'contain the stripacl option.'
            )

        return self


class FilesystemSetPermResult(BaseModel):
    result: Literal[None]
