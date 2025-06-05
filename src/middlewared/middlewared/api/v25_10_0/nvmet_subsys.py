from typing import Literal, Optional

from pydantic import Field

from middlewared.api.base import NQN, BaseModel, Excluded, ForUpdateMetaclass, NonEmptyString, excluded_field

__all__ = [
    "NVMetSubsysEntry",
    "NVMetSubsysCreateArgs",
    "NVMetSubsysCreateResult",
    "NVMetSubsysUpdateArgs",
    "NVMetSubsysUpdateResult",
    "NVMetSubsysDeleteArgs",
    "NVMetSubsysDeleteResult",
]


class NVMetSubsysEntry(BaseModel):
    id: int
    name: NonEmptyString
    """
    Human readable name for the subsystem.

    If `subnqn` is not provided on creation, then this name will be appended to the `basenqn` from \
    `nvmet.global.config` to generate a subnqn.
    """
    subnqn: NonEmptyString | None = None
    serial: str
    allow_any_host: bool = False
    """Any host can access the storage associated with this subsystem (i.e. no access control)."""
    pi_enable: bool | None = None
    qid_max: int | None = None
    ieee_oui: str | None = None
    ana: bool | None = None
    """
    If set to either `True` or `False`, then *override* the global `ana` setting from `nvmet.global.config` for this \
    subsystem only.

    If `null`, then the global `ana` setting will take effect.
    """
    hosts: Optional[list[int]] = []
    """
    List of host ids which have access to this subsystem.

    Only populated on query if `extra.options.verbose` is set.
    """
    namespaces: Optional[list[int]] = []
    """
    List of namespaces ids in this subsystem.

    Only populated on query if `extra.options.verbose` is set.
    """
    ports: Optional[list[int]] = []
    """
    List of ports ids on which this subsystem is available.

    Only populated on query if `extra.options.verbose` is set.
    """


class NVMetSubsysCreate(NVMetSubsysEntry):
    id: Excluded = excluded_field()
    serial: Excluded = excluded_field()
    hosts: Excluded = excluded_field()
    namespaces: Excluded = excluded_field()
    ports: Excluded = excluded_field()
    subnqn: NQN | None = None


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
    """ Force subsystem deletion, even if currently associated with one or more namespaces or ports. """


class NVMetSubsysDeleteArgs(BaseModel):
    id: int
    options: NVMetSubsysDeleteOptions = Field(default_factory=NVMetSubsysDeleteOptions)


class NVMetSubsysDeleteResult(BaseModel):
    result: Literal[True]
