from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, NonEmptyString, excluded_field

__all__ = [
    "NVMetSubsysEntry",
    "NVMetSubsysCreateArgs",
    "NVMetSubsysCreateResult",
    "NVMetSubsysUpdateArgs",
    "NVMetSubsysUpdateResult",
    "NVMetSubsysDeleteArgs",
    "NVMetSubsysDeleteResult",
]

MAX_NQN_LEN = 223


class NVMetSubsysEntry(BaseModel):
    id: int
    name: NonEmptyString
    """
    Human readable name for the subsystem.

    If `subnqn` is not provided on creation, then this name will be appended to the `basenqn` from `nvmet.global.config` to generate a subnqn.
    """
    subnqn: Annotated[NonEmptyString, StringConstraints(max_length=MAX_NQN_LEN)] | None = None
    serial: str
    allow_any_host: bool = False
    """
    If `True` then any host can access the storage associated with this subsystem (i.e. no access control).
    """
    pi_enable: bool | None = None
    qid_max: int | None = None
    ieee_oui: str | None = None
    ana: bool | None = None
    """
    If set to either `True` or `False` then *override* the global `ana` setting from `nvmet.global.config` for this subsystem only.

    If `null` then the global `ana` setting will take effect.
    """


class NVMetSubsysCreate(NVMetSubsysEntry):
    id: Excluded = excluded_field()
    serial: Excluded = excluded_field()


class NVMetSubsysCreateArgs(BaseModel):
    nvmet_subsys_create: NVMetSubsysCreate


class NVMetSubsysCreateResult(BaseModel):
    result: NVMetSubsysEntry


class NVMetSubsysUpdate(NVMetSubsysCreate, metaclass=ForUpdateMetaclass):
    pass


class NVMetSubsysUpdateArgs(BaseModel):
    id: int
    nvmet_subsys_update: NVMetSubsysUpdate


class NVMetSubsysUpdateResult(BaseModel):
    result: NVMetSubsysEntry


class NVMetSubsysDeleteOptions(BaseModel):
    force: bool = False
    """ Optional `boolean` to force subsystem deletion, even if currently associated with one or more namespaces or ports. """


class NVMetSubsysDeleteArgs(BaseModel):
    id: int
    options: NVMetSubsysDeleteOptions = Field(default_factory=NVMetSubsysDeleteOptions)


class NVMetSubsysDeleteResult(BaseModel):
    result: Literal[True]
