from typing import Literal

from pydantic import Field

from middlewared.api.base import (BaseModel, Excluded, excluded_field, ForUpdateMetaclass, HttpUrl, NonEmptyString,
                                  Private, single_argument_args, single_argument_result)

__all__ = ["KeychainCredentialEntry",
           "KeychainCredentialCreateArgs", "KeychainCredentialCreateResult",
           "KeychainCredentialUpdateArgs", "KeychainCredentialUpdateResult",
           "KeychainCredentialDeleteArgs", "KeychainCredentialDeleteResult",
           "KeychainCredentialUsedByArgs", "KeychainCredentialUsedByResult",
           "KeychainCredentialGetOfTypeArgs", "KeychainCredentialGetOfTypeResult",
           "KeychainCredentialGenerateSSHKeyPairArgs", "KeychainCredentialGenerateSSHKeyPairResult",
           "KeychainCredentialRemoteSSHHostKeyScanArgs", "KeychainCredentialRemoteSSHHostKeyScanResult",
           "KeychainCredentialRemoteSSHSemiautomaticSetupArgs", "KeychainCredentialRemoteSSHSemiautomaticSetupResult",
           "KeychainCredentialSSHPairArgs", "KeychainCredentialSSHPairResult",
           "KeychainCredentialSetupSSHConnectionArgs", "KeychainCredentialSetupSSHConnectionResult"]


class KeychainCredentialEntry(BaseModel):
    id: int
    name: NonEmptyString
    type: str
    attributes: Private[dict]


class KeychainCredentialCreate(KeychainCredentialEntry):
    id: Excluded = excluded_field()


class KeychainCredentialUpdate(KeychainCredentialCreate, metaclass=ForUpdateMetaclass):
    type: Excluded = excluded_field()


class KeychainCredentialCreateArgs(BaseModel):
    keychain_credential_create: KeychainCredentialCreate


class KeychainCredentialCreateResult(BaseModel):
    result: KeychainCredentialEntry


class KeychainCredentialUpdateArgs(BaseModel):
    id: int
    keychain_credential_update: KeychainCredentialUpdate


class KeychainCredentialUpdateResult(BaseModel):
    result: KeychainCredentialEntry


class KeychainCredentialDeleteOptions(BaseModel):
    cascade: bool = False


class KeychainCredentialDeleteArgs(BaseModel):
    id: int
    options: KeychainCredentialDeleteOptions = Field(default=KeychainCredentialDeleteOptions())


class KeychainCredentialDeleteResult(BaseModel):
    result: None


class KeychainCredentialUsedByArgs(BaseModel):
    id: int


class UsedKeychainCredential(BaseModel):
    title: str
    unbind_method: Literal["delete", "disable"]


class KeychainCredentialUsedByResult(BaseModel):
    result: list[UsedKeychainCredential]


class KeychainCredentialGetOfTypeArgs(BaseModel):
    id: int
    type: str


@single_argument_result
class KeychainCredentialGetOfTypeResult(KeychainCredentialEntry):
    pass


class KeychainCredentialGenerateSSHKeyPairArgs(BaseModel):
    pass


@single_argument_result
class KeychainCredentialGenerateSSHKeyPairResult(BaseModel):
    private_key: str
    public_key: str


@single_argument_args("keychain_remote_ssh_host_key_scan")
class KeychainCredentialRemoteSSHHostKeyScanArgs(BaseModel):
    host: NonEmptyString
    port: int = 22
    connect_timeout: int = 10


class KeychainCredentialRemoteSSHHostKeyScanResult(BaseModel):
    result: str


@single_argument_args("keychain_remote_ssh_semiautomatic_setup")
class KeychainCredentialRemoteSSHSemiautomaticSetupArgs(BaseModel):
    name: NonEmptyString
    url: HttpUrl
    verify_ssl: bool = True
    token: Private[str | None] = None
    admin_username: str = "root"
    password: Private[str | None] = None
    otp_token: Private[str | None] = None
    username: str = "root"
    private_key: Private[int]
    connect_timeout: int = 10
    sudo: bool = False


class KeychainCredentialRemoteSSHSemiautomaticSetupResult(BaseModel):
    result: KeychainCredentialEntry


@single_argument_args("keychain_ssh_pair")
class KeychainCredentialSSHPairArgs(BaseModel):
    remote_hostname: NonEmptyString
    username: str = "root"
    public_key: NonEmptyString


class KeychainCredentialSSHPairResult(BaseModel):
    result: None


class KeychainCredentialSetupSSHConnectionPrivateKey(BaseModel):
    generate_key: bool = True
    existing_key_id: int | None = None
    name: NonEmptyString


class KeychainCredentialSetupSSHConnectionSemiAutomaticSetup(
    KeychainCredentialRemoteSSHSemiautomaticSetupArgs.model_fields["keychain_remote_ssh_semiautomatic_setup"].annotation
):
    name: Excluded = excluded_field()
    private_key: Excluded = excluded_field()


@single_argument_args("setup_ssh_connection")
class KeychainCredentialSetupSSHConnectionArgs(BaseModel):
    private_key: KeychainCredentialSetupSSHConnectionPrivateKey | None = None
    connection_name: NonEmptyString
    setup_type: Literal["SEMI-AUTOMATIC", "MANUAL"] = "MANUAL"
    semi_automatic_setup: KeychainCredentialSetupSSHConnectionSemiAutomaticSetup | None = None
    manual_setup: dict | None = None


@single_argument_result
class KeychainCredentialSetupSSHConnectionResult(KeychainCredentialEntry):
    pass
