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
    """Designates which node is forced to be MASTER when `disabled` is true \
    (i.e., when HA is administratively disabled). Evaluated relative to the \
    responding node: `true` means "this node is the pinned master," so the \
    peer observes the opposite value for the same underlying configuration. \
    Has no effect while `disabled` is false."""
    timeout: int
    """The time to WAIT (in seconds) until a failover occurs when a network \
    event occurs on an interface that is marked critical for failover AND \
    HA is enabled and working appropriately. The default time to wait is \
    2 seconds.

    **NOTE: This setting does NOT effect the `disabled` or `master` parameters.**
    """


class FailoverSyncToPeer(BaseModel):
    reboot: bool = False
    """Reboot the other controller after syncing."""


class FailoverUpdate(FailoverEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class FailoverUpgrade(BaseModel):
    train: NonEmptyString | None = None
    """Update train to use for the upgrade or `null` for default."""
    version: str | None = None
    """Specific version to upgrade to or `null` for latest."""
    resume: bool = False
    """Should be set to `true` if a previous call to this method returned a \
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
    """Note: the `failover.become_passive` method reboots the local node, so \
    the caller's WebSocket session is terminated and this response is not \
    normally delivered."""


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
    """Identifier of the current failover node: `A` (first chassis slot), \
    `B` (second chassis slot), or `MANUAL` (slot position could not be \
    determined, e.g., on non-HA hardware)."""


class FailoverStatusArgs(BaseModel):
    pass


class FailoverStatusResult(BaseModel):
    result: str
    """Current status of the failover system. One of:

    * `MASTER` - this node holds the VIPs and has the zpool(s) imported.
    * `BACKUP` - the peer is MASTER; this node is idle and ready to take over.
    * `ELECTING` - a failover event is in progress and the active node is being chosen.
    * `IMPORTING` - this node is in the process of becoming MASTER (importing zpool(s), starting services).
    * `ERROR` - neither node has the zpool(s) imported.
    * `SINGLE` - this is a non-HA system.
    * `UNKNOWN` - status could not be determined from local state and the peer queries failed."""


class FailoverSyncFromPeerArgs(BaseModel):
    pass


class FailoverSyncFromPeerResult(BaseModel):
    result: None
    """Returns `null` when the sync from peer operation completes. The call \
    blocks until the peer's `failover.sync_to_peer` finishes."""


class FailoverSyncToPeerArgs(BaseModel):
    options: FailoverSyncToPeer = FailoverSyncToPeer()
    """Options for syncing configuration to the peer node."""


class FailoverSyncToPeerResult(BaseModel):
    result: None
    """Returns `null` when the sync to peer operation completes."""


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
    """Returns `true` when the failover upgrade completes successfully. See \
    `failover.upgrade` for what constitutes completion."""


class FailoverStatusChangedEvent(BaseModel):
    fields: "FailoverStatusChangedEventFields"
    """Event fields."""


class FailoverStatusChangedEventFields(BaseModel):
    status: str
    """Current status of the failover system. See `failover.status` for the \
    complete list of possible values (`MASTER`, `BACKUP`, `ELECTING`, \
    `IMPORTING`, `ERROR`, `SINGLE`, `UNKNOWN`)."""
