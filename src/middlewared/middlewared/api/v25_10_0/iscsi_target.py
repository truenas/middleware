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
    """ID of the iSCSI portal to use for this target group."""
    initiator: int | None = None
    """ID of the authorized initiator group or `null` to allow any initiator."""
    authmethod: IscsiAuthType = 'NONE'
    """Authentication method for this target group."""
    auth: int | None = None
    """ID of the authentication credential or `null` if no authentication."""


class IscsiTargetParameters(BaseModel):
    QueuedCommands: Literal[32, 128] | None = None
    """Maximum number of queued commands per iSCSI session.

    * `32`: Standard queue depth for most use cases
    * `128`: Higher queue depth for performance-critical applications
    """


class iSCSITargetEntry(BaseModel):
    id: int
    """Unique identifier for the iSCSI target."""
    name: Annotated[NonEmptyString,
                    AfterValidator(
                        match_validator(
                            RE_TARGET_NAME,
                            "Name can only contain lowercase alphanumeric charactersplus dot (.), dash (-), and colon (:)",
                        )
                    ),
                    StringConstraints(max_length=120)]
    """Name of the iSCSI target (maximum 120 characters)."""
    alias: str | None = None
    """Optional alias name for the iSCSI target."""
    mode: Literal['ISCSI', 'FC', 'BOTH'] = 'ISCSI'
    """Protocol mode for the target.

    * `ISCSI`: iSCSI protocol only
    * `FC`: Fibre Channel protocol only
    * `BOTH`: Both iSCSI and Fibre Channel protocols

    Fibre Channel may only be selected on TrueNAS Enterprise-licensed systems with a suitable Fibre Channel HBA.
    """
    groups: list[IscsiGroup] = []
    """Array of portal-initiator group associations for this target."""
    auth_networks: list[str] = []  # IPvAnyNetwork: "Object of type IPv4Network is not JSON serializable", etc
    """Array of network addresses allowed to access this target."""
    rel_tgt_id: int
    """Relative target ID number assigned by the system."""
    iscsi_parameters: IscsiTargetParameters | None = None
    """Optional iSCSI-specific parameters for this target."""


class iSCSITargetValidateNameArgs(BaseModel):
    name: str
    """Target name to validate."""
    existing_id: int | None = None
    """ID of existing target to exclude from validation or `null` for new targets."""


class iSCSITargetValidateNameResult(BaseModel):
    result: str | None
    """Error message if name is invalid or `null` if name is valid."""


class IscsiTargetCreate(iSCSITargetEntry):
    id: Excluded = excluded_field()
    rel_tgt_id: Excluded = excluded_field()


class iSCSITargetCreateArgs(BaseModel):
    iscsi_target_create: IscsiTargetCreate
    """iSCSI target configuration data for creation."""


class iSCSITargetCreateResult(BaseModel):
    result: iSCSITargetEntry
    """The created iSCSI target configuration."""


class IscsiTargetUpdate(IscsiTargetCreate, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetUpdateArgs(BaseModel):
    id: int
    """ID of the iSCSI target to update."""
    iscsi_target_update: IscsiTargetUpdate
    """Updated iSCSI target configuration data."""


class iSCSITargetUpdateResult(BaseModel):
    result: iSCSITargetEntry
    """The updated iSCSI target configuration."""


class iSCSITargetDeleteArgs(BaseModel):
    id: int
    """ID of the iSCSI target to delete."""
    force: bool = False
    """Whether to force deletion even if the target is in use."""
    delete_extents: bool = False
    """Whether to also delete associated extents."""


class iSCSITargetDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the iSCSI target is successfully deleted."""
