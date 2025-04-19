from typing import Literal

from pydantic import Field, Secret

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, NonEmptyString, excluded_field

__all__ = [
    "NVMetHostEntry",
    "NVMetHostCreateArgs",
    "NVMetHostCreateResult",
    "NVMetHostUpdateArgs",
    "NVMetHostUpdateResult",
    "NVMetHostDeleteArgs",
    "NVMetHostDeleteResult",
    "NVMetHostGenerateKeyArgs",
    "NVMetHostGenerateKeyResult"
]


class NVMetHostEntry(BaseModel):
    id: int
    hostnqn: NonEmptyString
    """ NQN of the host that will connect to this TrueNAS. """
    dhchap_key: Secret[NonEmptyString | None] = None
    """
    If set, the secret that the host must present when connecting.

    A suitable secret can be generated using `nvme gen-dhchap-key`, or by using the `nvmet.host.generate_key` API.
    """
    dhchap_ctrl_key: Secret[NonEmptyString | None] = None
    """
    If set, the secret that this TrueNAS will present to the host when the host is connecting (Bi-Directional Authentication).

    A suitable secret can be generated using `nvme gen-dhchap-key`, or by using the `nvmet.host.generate_key` API.
    """
    dhchap_dhgroup: Literal['2048-BIT', '3072-BIT', '4096-BIT', '6144-BIT', '8192-BIT'] | None = None
    """
    If selected, the DH (Diffie-Hellman) key exchange built on top of CHAP to be used for authentication.
    """
    dhchap_hash: Literal['SHA-256', 'SHA-384', 'SHA-512'] = 'SHA-256'
    """
    HMAC (Hashed Message Authentication Code) to be used in conjunction if a `dhchap_dhgroup` is selected.
    """


class NVMetHostCreate(NVMetHostEntry):
    id: Excluded = excluded_field()


class NVMetHostCreateArgs(BaseModel):
    nvmet_host_create: NVMetHostCreate


class NVMetHostCreateResult(BaseModel):
    result: NVMetHostEntry


class NVMetHostUpdate(NVMetHostCreate, metaclass=ForUpdateMetaclass):
    pass


class NVMetHostUpdateArgs(BaseModel):
    id: int
    nvmet_host_update: NVMetHostUpdate


class NVMetHostUpdateResult(BaseModel):
    result: NVMetHostEntry


class NVMetHostDeleteOptions(BaseModel):
    force: bool = False
    """ Optional `boolean` to force host deletion, even if currently associated with one or more subsystems. """


class NVMetHostDeleteArgs(BaseModel):
    id: int
    options: NVMetHostDeleteOptions = Field(default_factory=NVMetHostDeleteOptions)


class NVMetHostDeleteResult(BaseModel):
    result: Literal[True]


class NVMetHostGenerateKeyArgs(BaseModel):
    dhchap_hash: Literal['SHA-256', 'SHA-384', 'SHA-512'] = 'SHA-256'
    """ Hash to be used with the generated key.  """
    nqn: str = None
    """ NQN to be used for the transformation. """


class NVMetHostGenerateKeyResult(BaseModel):
    result: str
