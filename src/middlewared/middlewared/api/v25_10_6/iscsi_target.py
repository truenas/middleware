import re
from typing import Literal

from pydantic import AfterValidator, Field, StringConstraints
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
    portal: int = Field(description="ID of the iSCSI portal to use for this target group.")
    initiator: int | None = Field(
        default=None,
        description="ID of the authorized initiator group or `null` to allow any initiator.",
    )
    authmethod: IscsiAuthType = Field(default='NONE', description="Authentication method for this target group.")
    auth: int | None = Field(
        default=None,
        description="ID of the authentication credential or `null` if no authentication.",
    )


class IscsiTargetParameters(BaseModel):
    QueuedCommands: Literal[32, 128] | None = Field(
        default=None,
        description=(
            "Maximum number of queued commands per iSCSI session.\n"
            "\n"
            "* `32`: Standard queue depth for most use cases\n"
            "* `128`: Higher queue depth for performance-critical applications"
        ),
    )


class iSCSITargetEntry(BaseModel):
    id: int = Field(description="Unique identifier for the iSCSI target.")
    name: Annotated[
        NonEmptyString,
        AfterValidator(
            match_validator(
                RE_TARGET_NAME,
                "Name can only contain lowercase alphanumeric charactersplus dot (.), dash (-), and colon (:)",
            )
        ),
        StringConstraints(max_length=120)
    ] = Field(description="Name of the iSCSI target (maximum 120 characters).")
    alias: str | None = Field(default=None, description="Optional alias name for the iSCSI target.")
    mode: Literal['ISCSI', 'FC', 'BOTH'] = Field(
        default='ISCSI',
        description=(
            "Protocol mode for the target.\n"
            "\n"
            "* `ISCSI`: iSCSI protocol only\n"
            "* `FC`: Fibre Channel protocol only\n"
            "* `BOTH`: Both iSCSI and Fibre Channel protocols\n"
            "\n"
            "Fibre Channel may only be selected on TrueNAS Enterprise-licensed systems with a suitable Fibre Channel "
            "HBA."
        ),
    )
    groups: list[IscsiGroup] = Field(
        default=[],
        description="Array of portal-initiator group associations for this target.",
    )
    auth_networks: list[str] = Field(
        default=[],
        description="Array of network addresses allowed to access this target.",
    )  # IPvAnyNetwork: "Object of type IPv4Network is not JSON serializable", etc
    rel_tgt_id: int = Field(description="Relative target ID number assigned by the system.")
    iscsi_parameters: IscsiTargetParameters | None = Field(
        default=None,
        description="Optional iSCSI-specific parameters for this target.",
    )


class iSCSITargetValidateNameArgs(BaseModel):
    name: str = Field(description="Target name to validate.")
    existing_id: int | None = Field(
        default=None,
        description="ID of existing target to exclude from validation or `null` for new targets.",
    )


class iSCSITargetValidateNameResult(BaseModel):
    result: str | None = Field(description="Error message if name is invalid or `null` if name is valid.")


class IscsiTargetCreate(iSCSITargetEntry):
    id: Excluded = excluded_field()
    rel_tgt_id: Excluded = excluded_field()


class iSCSITargetCreateArgs(BaseModel):
    iscsi_target_create: IscsiTargetCreate = Field(description="iSCSI target configuration data for creation.")


class iSCSITargetCreateResult(BaseModel):
    result: iSCSITargetEntry = Field(description="The created iSCSI target configuration.")


class IscsiTargetUpdate(IscsiTargetCreate, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetUpdateArgs(BaseModel):
    id: int = Field(description="ID of the iSCSI target to update.")
    iscsi_target_update: IscsiTargetUpdate = Field(description="Updated iSCSI target configuration data.")


class iSCSITargetUpdateResult(BaseModel):
    result: iSCSITargetEntry = Field(description="The updated iSCSI target configuration.")


class iSCSITargetDeleteArgs(BaseModel):
    id: int = Field(description="ID of the iSCSI target to delete.")
    force: bool = Field(default=False, description="Whether to force deletion even if the target is in use.")
    delete_extents: bool = Field(default=False, description="Whether to also delete associated extents.")


class iSCSITargetDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the iSCSI target is successfully deleted.")
