
from pydantic import Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    NonEmptyString,
    excluded_field,
)

__all__ = [
    "FailoverEntry", "FailoverBecomePassiveArgs", "FailoverBecomePassiveResult", "FailoverGetIpsArgs",
    "FailoverGetIpsResult", "FailoverLicensedArgs", "FailoverLicensedResult", "FailoverNodeArgs", "FailoverNodeResult",
    "FailoverStatusArgs", "FailoverStatusResult", "FailoverSyncFromPeerArgs", "FailoverSyncFromPeerResult",
    "FailoverSyncToPeerArgs", "FailoverSyncToPeerResult", "FailoverUpdateArgs", "FailoverUpdateResult",
    "FailoverUpgradeArgs", "FailoverUpgradeResult", "FailoverStatusChangedEvent",
]


class FailoverEntry(BaseModel):
    id: int = Field(description="Unique identifier for the failover configuration.")
    disabled: bool = Field(description="When true, HA will be administratively disabled.")
    master: bool = Field(
        description=(
            "Marks the particular node in the chassis as the master node. The standby node will have the opposite "
            "value."
        ),
    )
    timeout: int = Field(
        description=(
            "The time to WAIT (in seconds) until a failover occurs when a network event occurs on an interface that is "
            "marked critical for failover AND HA is enabled and working appropriately. The default time to wait is 2 "
            "seconds.\n"
            "\n"
            "**NOTE: This setting does NOT effect the `disabled` or `master` parameters.**"
        ),
    )


class FailoverSyncToPeer(BaseModel):
    reboot: bool = Field(default=False, description="Reboot the other controller.")


class FailoverUpdate(FailoverEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class FailoverUpgrade(BaseModel):
    train: NonEmptyString | None = Field(
        default=None,
        description="Update train to use for the upgrade or `null` for default.",
    )
    version: str | None = Field(default=None, description="Specific version to upgrade to or `null` for latest.")
    resume: bool = Field(
        default=False,
        description=(
            "Should be set to true if a previous call to this method returned a `CallError` with `errno=EAGAIN` meaning"
            " that an upgrade can be performed with a warning and that warning is accepted. In that case, you also have"
            " to set `resume_manual` to `true` if a previous call to this method was performed using update file "
            "upload."
        ),
    )
    resume_manual: bool = Field(default=False, description="Whether to resume a manual upgrade operation.")


class FailoverBecomePassiveArgs(BaseModel):
    pass


class FailoverBecomePassiveResult(BaseModel):
    result: None = Field(description="Returns `null` when the node successfully becomes passive.")


class FailoverGetIpsArgs(BaseModel):
    pass


class FailoverGetIpsResult(BaseModel):
    result: list[str] = Field(description="Array of IP addresses configured for failover.")


class FailoverLicensedArgs(BaseModel):
    pass


class FailoverLicensedResult(BaseModel):
    result: bool = Field(
        description="Returns `true` if the system is licensed for high availability, `false` otherwise.",
    )


class FailoverNodeArgs(BaseModel):
    pass


class FailoverNodeResult(BaseModel):
    result: str = Field(description="Identifier of the current failover node (A or B).")


class FailoverStatusArgs(BaseModel):
    pass


class FailoverStatusResult(BaseModel):
    result: str = Field(description="Current status of the failover system.")


class FailoverSyncFromPeerArgs(BaseModel):
    pass


class FailoverSyncFromPeerResult(BaseModel):
    result: None = Field(description="Returns `null` when the sync from peer operation is successfully started.")


class FailoverSyncToPeerArgs(BaseModel):
    options: FailoverSyncToPeer = Field(
        default=FailoverSyncToPeer(),
        description="Options for syncing configuration to the peer node.",
    )


class FailoverSyncToPeerResult(BaseModel):
    result: None = Field(description="Returns `null` when the sync to peer operation is successfully started.")


class FailoverUpdateArgs(BaseModel):
    data: FailoverUpdate = Field(description="Updated failover configuration data.")


class FailoverUpdateResult(BaseModel):
    result: FailoverEntry = Field(description="The updated failover configuration.")


class FailoverUpgradeArgs(BaseModel):
    failover_upgrade: FailoverUpgrade = Field(
        default=FailoverUpgrade(),
        description="Failover upgrade configuration options.",
    )


class FailoverUpgradeResult(BaseModel):
    result: bool = Field(description="Returns `true` when the failover upgrade is successfully initiated.")


class FailoverStatusChangedEvent(BaseModel):
    fields: "FailoverStatusChangedEventFields" = Field(description="Event fields.")


class FailoverStatusChangedEventFields(BaseModel):
    status: str = Field(description="Current status of the failover system.")
