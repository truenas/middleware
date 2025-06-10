import re
from typing import Literal

from pydantic import AfterValidator, StringConstraints
from typing_extensions import Annotated

from middlewared.api.base import (BaseModel, Excluded, ForUpdateMetaclass, IscsiAuthType, NonEmptyString,
                                  excluded_field, match_validator)

RE_TARGET_NAME = re.compile(r'^[-a-z0-9\.:]+$')

__all__ = [
    "IscsiTargetEntry",
    "IscsiTargetValidateNameArgs",
    "IscsiTargetValidateNameResult",
    "IscsiTargetCreateArgs",
    "IscsiTargetCreateResult",
    "IscsiTargetUpdateArgs",
    "IscsiTargetUpdateResult",
    "IscsiTargetDeleteArgs",
    "IscsiTargetDeleteResult",
]


class IscsiGroup(BaseModel):
    portal: int
    initiator: int | None = None
    authmethod: IscsiAuthType = 'NONE'
    auth: int | None = None


class IscsiTargetParameters(BaseModel):
    QueuedCommands: Literal[32, 128] | None = None


class IscsiTargetEntry(BaseModel):
    id: int
    name: Annotated[NonEmptyString,
                    AfterValidator(
                        match_validator(
                            RE_TARGET_NAME,
                            "Name can only contain lowercase alphanumeric charactersplus dot (.), dash (-), and colon (:)",
                        )
                    ),
                    StringConstraints(max_length=120)]
    alias: str | None = None
    mode: Literal['ISCSI', 'FC', 'BOTH'] = 'ISCSI'
    groups: list[IscsiGroup] = []
    auth_networks: list[str] = []  # IPvAnyNetwork: "Object of type IPv4Network is not JSON serializable", etc
    rel_tgt_id: int
    iscsi_parameters: IscsiTargetParameters | None = None


class IscsiTargetValidateNameArgs(BaseModel):
    name: str
    existing_id: int | None = None


class IscsiTargetValidateNameResult(BaseModel):
    result: str | None


class IscsiTargetCreate(IscsiTargetEntry):
    id: Excluded = excluded_field()
    rel_tgt_id: Excluded = excluded_field()
    defer: bool = False


class IscsiTargetCreateArgs(BaseModel):
    iscsi_target_create: IscsiTargetCreate


class IscsiTargetCreateResult(BaseModel):
    result: IscsiTargetEntry


class IscsiTargetUpdate(IscsiTargetCreate, metaclass=ForUpdateMetaclass):
    pass


class IscsiTargetUpdateArgs(BaseModel):
    id: int
    iscsi_target_update: IscsiTargetUpdate


class IscsiTargetUpdateResult(BaseModel):
    result: IscsiTargetEntry


class IscsiTargetDeleteArgs(BaseModel):
    id: int
    force: bool = False
    delete_extents: bool = False
    defer: bool = False


class IscsiTargetDeleteResult(BaseModel):
    result: Literal[True]
