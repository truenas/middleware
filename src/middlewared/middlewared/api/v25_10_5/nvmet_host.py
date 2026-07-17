from typing import Literal, TypeAlias

from pydantic import Field, Secret, model_validator

from middlewared.api.base import NQN, BaseModel, Excluded, ForUpdateMetaclass, NonEmptyString, excluded_field

__all__ = [
    "NVMetHostEntry",
    "NVMetHostCreateArgs",
    "NVMetHostCreateResult",
    "NVMetHostUpdateArgs",
    "NVMetHostUpdateResult",
    "NVMetHostDeleteArgs",
    "NVMetHostDeleteResult",
    "NVMetHostGenerateKeyArgs",
    "NVMetHostGenerateKeyResult",
    "NVMetHostDhchapDhgroupChoicesArgs",
    "NVMetHostDhchapDhgroupChoicesResult",
    "NVMetHostDhchapHashChoicesArgs",
    "NVMetHostDhchapHashChoicesResult",
]

DHChapHashType: TypeAlias = Literal['SHA-256', 'SHA-384', 'SHA-512']
DHChapDHGroupType: TypeAlias = Literal['2048-BIT', '3072-BIT', '4096-BIT', '6144-BIT', '8192-BIT']


class NVMetHostEntry(BaseModel):
    id: int = Field(description="Unique identifier for the NVMe-oF host.")
    hostnqn: NonEmptyString = Field(description="NQN of the host that will connect to this TrueNAS.")
    dhchap_key: Secret[NonEmptyString | None] = Field(
        default=None,
        description=(
            "If set, the secret that the host must present when connecting.\n"
            "\n"
            "A suitable secret can be generated using `nvme gen-dhchap-key`, or by using the `nvmet.host.generate_key` "
            "API."
        ),
    )
    dhchap_ctrl_key: Secret[NonEmptyString | None] = Field(
        default=None,
        description=(
            "If set, the secret that this TrueNAS will present to the host when the host is connecting (Bi-Directional "
            "Authentication).\n"
            "\n"
            "A suitable secret can be generated using `nvme gen-dhchap-key`, or by using the `nvmet.host.generate_key` "
            "API."
        ),
    )
    dhchap_dhgroup: DHChapDHGroupType | None = Field(
        default=None,
        description=(
            "If selected, the DH (Diffie-Hellman) key exchange built on top of CHAP to be used for authentication."
        ),
    )
    dhchap_hash: DHChapHashType = Field(
        default='SHA-256',
        description=(
            "HMAC (Hashed Message Authentication Code) to be used in conjunction if a `dhchap_dhgroup` is selected."
        ),
    )


class NVMetHostCreate(NVMetHostEntry):
    id: Excluded = excluded_field()
    hostnqn: NQN

    @model_validator(mode='after')
    def validate_attrs(self):
        if self.dhchap_ctrl_key and not self.dhchap_key:
            raise ValueError('Cannot configure bi-directional authentication without setting dhchap_key')

        return self


class NVMetHostCreateArgs(BaseModel):
    nvmet_host_create: NVMetHostCreate = Field(description="NVMe-oF host configuration data for creation.")


class NVMetHostCreateResult(BaseModel):
    result: NVMetHostEntry = Field(description="The created NVMe-oF host configuration.")


class NVMetHostUpdate(NVMetHostCreate, metaclass=ForUpdateMetaclass):
    pass


class NVMetHostUpdateArgs(BaseModel):
    id: int = Field(description="ID of the NVMe-oF host to update.")
    nvmet_host_update: NVMetHostUpdate = Field(description="Updated NVMe-oF host configuration data.")


class NVMetHostUpdateResult(BaseModel):
    result: NVMetHostEntry = Field(description="The updated NVMe-oF host configuration.")


class NVMetHostDeleteOptions(BaseModel):
    force: bool = Field(
        default=False,
        description="Force host deletion, even if currently associated with one or more subsystems.",
    )


class NVMetHostDeleteArgs(BaseModel):
    id: int = Field(description="ID of the NVMe-oF host to delete.")
    options: NVMetHostDeleteOptions = Field(
        default_factory=NVMetHostDeleteOptions,
        description="Options controlling host deletion behavior.",
    )


class NVMetHostDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the NVMe-oF host is successfully deleted.")


class NVMetHostGenerateKeyArgs(BaseModel):
    dhchap_hash: DHChapHashType = Field(default='SHA-256', description="Hash to be used with the generated key.")
    nqn: str | None = Field(default=None, description="NQN to be used for the transformation.")


class NVMetHostGenerateKeyResult(BaseModel):
    result: str = Field(description="Generated DH-CHAP key for NVMe-oF authentication.")


class NVMetHostDhchapDhgroupChoicesArgs(BaseModel):
    pass


class NVMetHostDhchapDhgroupChoicesResult(BaseModel):
    result: list[DHChapDHGroupType] = Field(description="Array of available DH-CHAP Diffie-Hellman group options.")


class NVMetHostDhchapHashChoicesArgs(BaseModel):
    pass


class NVMetHostDhchapHashChoicesResult(BaseModel):
    result: list[DHChapHashType] = Field(description="Array of available DH-CHAP hash algorithm options.")
