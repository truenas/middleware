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
    "FailoverUpgradeArgs", "FailoverUpgradeResult",
]


class FailoverEntry(BaseModel):
    id: int
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
    version: str | None = None
    resume: bool = False
    """Should be set to true if a previous call to this method returned a \
    `CallError` with `errno=EAGAIN` meaning that an upgrade can be performed \
    with a warning and that warning is accepted. In that case, you also have \
    to set `resume_manual` to `true` if a previous call to this method was \
    performed using update file upload."""
    resume_manual: bool = False


class FailoverBecomePassiveArgs(BaseModel):
    pass


class FailoverBecomePassiveResult(BaseModel):
    result: None


class FailoverGetIpsArgs(BaseModel):
    pass


class FailoverGetIpsResult(BaseModel):
    result: list[str]


class FailoverLicensedArgs(BaseModel):
    pass


class FailoverLicensedResult(BaseModel):
    result: bool


class FailoverNodeArgs(BaseModel):
    pass


class FailoverNodeResult(BaseModel):
    result: str


class FailoverStatusArgs(BaseModel):
    pass


class FailoverStatusResult(BaseModel):
    result: str


class FailoverSyncFromPeerArgs(BaseModel):
    pass


class FailoverSyncFromPeerResult(BaseModel):
    result: None


class FailoverSyncToPeerArgs(BaseModel):
    options: FailoverSyncToPeer = FailoverSyncToPeer()


class FailoverSyncToPeerResult(BaseModel):
    result: None


class FailoverUpdateArgs(BaseModel):
    data: FailoverUpdate


class FailoverUpdateResult(BaseModel):
    result: FailoverEntry


class FailoverUpgradeArgs(BaseModel):
    failover_upgrade: FailoverUpgrade = FailoverUpgrade()


class FailoverUpgradeResult(BaseModel):
    result: bool
