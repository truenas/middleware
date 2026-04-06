from __future__ import annotations

from middlewared.api.base import BaseModel, LongString


class JWKCreate(BaseModel):
    key_size: int = 2048
    public_exponent: int = 65537


class ACMERegistrationBody(BaseModel):
    id: int
    status: str
    key: LongString


class ACMERegistrationEntry(BaseModel):
    id: int
    uri: str
    directory: str
    tos: str
    new_account_uri: str
    new_nonce_uri: str
    new_order_uri: str
    revoke_cert_uri: str
    body: ACMERegistrationBody


class ACMERegistrationCreate(BaseModel):
    tos: bool = False
    JWK_create: JWKCreate = JWKCreate()
    acme_directory_uri: str


class ACMERegistrationCreateArgs(BaseModel):
    acme_registration_create: ACMERegistrationCreate


class ACMERegistrationCreateResult(BaseModel):
    result: ACMERegistrationEntry
