from middlewared.api.base import BaseModel, NotRequired, single_argument_args

from pydantic import HttpUrl


class FailoverGetIpsArgs(BaseModel):
    pass


class FailoverGetIpsResult(BaseModel):
    result: list[HttpUrl]


class FailoverBecomePassiveArgs(BaseModel):
    pass


class FailoverBecomePassiveResult(BaseModel):
    result: None


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
    result: str

@single_argument_args("sync_to_peer")
class FailoverSyncToPeerArgs(BaseModel):
    reboot: bool = False
    """If set to True, will reboot the other controller."""


class FailoverSyncToPeerResult(BaseModel):
    result: None


class FailoverUpdateEntry(BaseModel):
    id: int
    disabled: bool
    master: bool
    timeout: int


@single_argument_args("failover_update")
class FailoverUpdateArgs(BaseModel):
    disabled: bool
    """When true HA will be administratively disabled."""
    master: bool = NotRequired
    """Marks the particular node in the chassis as the master node.
    The standby node will have the opposite value."""
    timeout: int
    """The time to WAIT (in seconds) until a failover occurs when a network
    event occurs on an interface that is marked critical for failover AND
    HA is enabled and working appropriately. The default time to wait is
    2 seconds.
    
    **NOTE**
        This setting does NOT effect the `disabled` or `master` parameters."""


class FailoverUpdateResult(BaseModel):
    result: FailoverUpdateEntry


class FailoverUpgradeArgs(BaseModel):
    train: str = NotRequired
    resume: bool = False
    """Should be set to true if a previous call to this method returned a
    `CallError` with `errno=EAGAIN` meaning that an upgrade can be performed
    with a warning and that warning is accepted. In that case, you also have
    to set `resume_manual` to `true` if a previous call to this method was
    performed using update file upload."""
    resume_manual: bool = False


class FailoverUpgradeResult(BaseModel):
    result: bool
