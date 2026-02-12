from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    NonEmptyString,
)


__all__ = [
    "FailoverEntry", "FailoverBecomePassiveArgs", "FailoverBecomePassiveResult", "FailoverGetIpsArgs",
    "FailoverGetIpsResult", "FailoverLicensedArgs", "FailoverLicensedResult", "FailoverNodeArgs", "FailoverNodeResult",
    "FailoverStatusArgs", "FailoverStatusResult", "FailoverSyncFromPeerArgs", "FailoverSyncFromPeerResult",
    "FailoverSyncToPeerArgs", "FailoverSyncToPeerResult", "FailoverUpdateArgs", "FailoverUpdateResult",
    "FailoverUpgradeArgs", "FailoverUpgradeResult", "FailoverStatusChangedEvent",
]


class FailoverEntry(BaseModel):
    id: int
    """Unique identifier for the failover configuration."""
    disabled: bool
    """When true, HA will be administratively disabled."""
    master: bool
    """Marks the particular node in the chassis as the master node. \
    The standby node will have the opposite value."""
    timeout: int
    """The time to WAIT (in seconds) until a failover occurs when a network \
    event occurs on an interface that is marked critical for failover AND \
    HA is enabled and working appropriately. The default time to wait is \
    2 seconds.

    **NOTE: This setting does NOT effect the `disabled` or `master` parameters.**
    """


class FailoverSyncToPeer(BaseModel):
    reboot: bool = False
    """Reboot the other controller."""


class FailoverUpdate(FailoverEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class FailoverUpgrade(BaseModel):
    train: NonEmptyString | None = None
    """Update train to use for the upgrade or `null` for default."""
    version: str | None = None
    """Specific version to upgrade to or `null` for latest."""
    resume: bool = False
    """Should be set to true if a previous call to this method returned a \
    `CallError` with `errno=EAGAIN` meaning that an upgrade can be performed \
    with a warning and that warning is accepted. In that case, you also have \
    to set `resume_manual` to `true` if a previous call to this method was \
    performed using update file upload."""
    resume_manual: bool = False
    """Whether to resume a manual upgrade operation."""


class FailoverBecomePassiveArgs(BaseModel):
    pass


class FailoverBecomePassiveResult(BaseModel):
    result: None
    """Returns `null` when the node successfully becomes passive."""


class FailoverGetIpsArgs(BaseModel):
    pass


class FailoverGetIpsResult(BaseModel):
    result: list[str]
    """Array of IP addresses configured for failover."""


class FailoverLicensedArgs(BaseModel):
    pass


class FailoverLicensedResult(BaseModel):
    result: bool
    """Returns `true` if the system is licensed for high availability, `false` otherwise."""


class FailoverNodeArgs(BaseModel):
    pass


class FailoverNodeResult(BaseModel):
    result: str
    """Identifier of the current failover node (A or B)."""


class FailoverStatusArgs(BaseModel):
    pass


class FailoverStatusResult(BaseModel):
    result: str
    """Current status of the failover system."""


class FailoverSyncFromPeerArgs(BaseModel):
    pass


class FailoverSyncFromPeerResult(BaseModel):
    result: None
    """Returns `null` when the sync from peer operation is successfully started."""


class FailoverSyncToPeerArgs(BaseModel):
    options: FailoverSyncToPeer = FailoverSyncToPeer()
    """Options for syncing configuration to the peer node."""


class FailoverSyncToPeerResult(BaseModel):
    result: None
    """Returns `null` when the sync to peer operation is successfully started."""


class FailoverUpdateArgs(BaseModel):
    data: FailoverUpdate
    """Updated failover configuration data."""


class FailoverUpdateResult(BaseModel):
    result: FailoverEntry
    """The updated failover configuration."""


class FailoverUpgradeArgs(BaseModel):
    failover_upgrade: FailoverUpgrade = FailoverUpgrade()
    """Failover upgrade configuration options."""


class FailoverUpgradeResult(BaseModel):
    result: bool
    """Returns `true` when the failover upgrade is successfully initiated."""


class FailoverStatusChangedEvent(BaseModel):
    fields: "FailoverStatusChangedEventFields"
    """Event fields."""


class FailoverStatusChangedEventFields(BaseModel):
    status: str
    """Current status of the failover system."""
