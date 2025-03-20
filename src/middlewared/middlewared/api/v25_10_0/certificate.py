from pydantic import Field

from middlewared.api.base import (
    BaseModel, single_argument_args, ForUpdateMetaclass, LongString, NonEmptyString,
)


__all__ = [
    'CertificateEntry',
]


class CertificateEntry(BaseModel):
    id: int
    type: int
    name: NonEmptyString
    certificate: LongString | None
    privatekey: LongString | None
    CSR: LongString | None
    acme_uri: str | None
    domains_authenticators: dict | None
    renew_days: int
    root_path: NonEmptyString
    acme: dict | None
    certificate_path: NonEmptyString | None
    privatekey_path: NonEmptyString | None
    csr_path: NonEmptyString | None
    cert_type: NonEmptyString
    expired: bool | None
    chain_list: list[str]
    country: str | None
    state: str | None
    city: str | None
    organization: str | None
    organizational_unit: str | None
    san: list[str] | None
    email: str | None
    DN: str | None
    subject_name_hash: str | None
    digest_algorithm: str | None
    from_: str | None = Field(alias='from')
    common: str | None
    until: str | None
    fingerprint: str | None
    key_type: NonEmptyString | None
    lifetime: int | None
    serial: int | None
    key_length: int | None
    add_to_trusted_store: bool
    chain: bool | None  # FIXME: Check usages and if it is reported correctly now
    cert_type_existing: bool
    cert_type_CSR: bool
    parsed: bool
    extensions: dict
