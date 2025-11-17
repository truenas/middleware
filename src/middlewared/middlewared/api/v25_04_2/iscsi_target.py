import re
from typing import Literal

from pydantic import AfterValidator, StringConstraints
from typing_extensions import Annotated

from middlewared.api.base import (BaseModel, Excluded, ForUpdateMetaclass, IscsiAuthType, NonEmptyString,
                                  excluded_field, match_validator)

RE_TARGET_NAME = re.compile(r'^[-a-z0-9\.:]+$')

__all__ = [
    "iSCSITargetEntry",
    "iSCSITargetValidateNameArgs",
    "iSCSITargetValidateNameResult",
    "iSCSITargetCreateArgs",
    "iSCSITargetCreateResult",
    "iSCSITargetUpdateArgs",
    "iSCSITargetUpdateResult",
    "iSCSITargetDeleteArgs",
    "iSCSITargetDeleteResult",
]


class IscsiGroup(BaseModel):
    portal: int
    initiator: int | None = None
    authmethod: IscsiAuthType = 'NONE'
    auth: int | None = None


class IscsiTargetParameters(BaseModel):
    QueuedCommands: Literal[32, 128] | None = None


class iSCSITargetEntry(BaseModel):
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


class iSCSITargetValidateNameArgs(BaseModel):
    name: str
    existing_id: int | None = None


class iSCSITargetValidateNameResult(BaseModel):
    result: str | None


class IscsiTargetCreate(iSCSITargetEntry):
    id: Excluded = excluded_field()
    rel_tgt_id: Excluded = excluded_field()


class iSCSITargetCreateArgs(BaseModel):
    iscsi_target_create: IscsiTargetCreate


class iSCSITargetCreateResult(BaseModel):
    result: iSCSITargetEntry


class IscsiTargetUpdate(IscsiTargetCreate, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetUpdateArgs(BaseModel):
    id: int
    iscsi_target_update: IscsiTargetUpdate


class iSCSITargetUpdateResult(BaseModel):
    result: iSCSITargetEntry


class iSCSITargetDeleteArgs(BaseModel):
    id: int
    force: bool = False
    delete_extents: bool = False


class iSCSITargetDeleteResult(BaseModel):
    result: Literal[True]
