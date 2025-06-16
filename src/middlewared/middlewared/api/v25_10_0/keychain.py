import abc
from typing import Annotated, Literal, Union

from pydantic import Discriminator, Secret

from middlewared.api.base import (BaseModel, Excluded, excluded_field, ForUpdateMetaclass, HttpUrl, LongString,
                                  NonEmptyString, single_argument_args, single_argument_result)

__all__ = ["KeychainCredentialEntry", "SSHKeyPairEntry", "SSHCredentialsEntry",
           "KeychainCredentialCreateArgs", "KeychainCredentialCreateResult",
           "KeychainCredentialUpdateArgs", "KeychainCredentialUpdateResult",
           "KeychainCredentialDeleteArgs", "KeychainCredentialDeleteResult",
           "KeychainCredentialUsedByArgs", "KeychainCredentialUsedByResult",
           "KeychainCredentialGenerateSshKeyPairArgs", "KeychainCredentialGenerateSshKeyPairResult",
           "KeychainCredentialRemoteSshHostKeyScanArgs", "KeychainCredentialRemoteSshHostKeyScanResult",
           "KeychainCredentialRemoteSshSemiautomaticSetupArgs", "KeychainCredentialRemoteSshSemiautomaticSetupResult",
           "KeychainCredentialSetupSshConnectionArgs", "KeychainCredentialSetupSshConnectionResult"]


class SSHKeyPair(BaseModel):
    """At least one of the two keys must be provided on creation."""
    private_key: LongString | None = None
    public_key: LongString | None = None
    """Can be omitted and automatically derived from the private key."""


class SSHCredentials(BaseModel):
    host: str
    port: int = 22
    username: str = "root"
    private_key: int
    """Keychain Credential ID."""
    remote_host_key: str
    """Can be discovered with keychaincredential.remote_ssh_host_key_scan."""
    connect_timeout: int = 10


class KeychainCredentialEntry(BaseModel, abc.ABC):
    id: int
    name: NonEmptyString
    """Distinguishes this Keychain Credential from others."""
    type: Literal["SSH_KEY_PAIR", "SSH_CREDENTIALS"]
    attributes: Secret[SSHKeyPair | SSHCredentials]


class SSHKeyPairEntry(KeychainCredentialEntry):
    type: Literal["SSH_KEY_PAIR"]
    attributes: Secret[SSHKeyPair]


class SSHCredentialsEntry(KeychainCredentialEntry):
    type: Literal["SSH_CREDENTIALS"]
    attributes: Secret[SSHCredentials]


class KeychainCredentialCreateSSHKeyPairEntry(SSHKeyPairEntry):
    id: Excluded = excluded_field()


class KeychainCredentialUpdateSSHKeyPairEntry(KeychainCredentialCreateSSHKeyPairEntry, metaclass=ForUpdateMetaclass):
    type: Excluded = excluded_field()


class KeychainCredentialCreateSSHCredentialsEntry(SSHCredentialsEntry):
    id: Excluded = excluded_field()


class KeychainCredentialUpdateSSHCredentialsEntry(
    KeychainCredentialCreateSSHCredentialsEntry,
    metaclass=ForUpdateMetaclass
):
    type: Excluded = excluded_field()


KeychainCredentialCreate = KeychainCredentialCreateSSHKeyPairEntry | KeychainCredentialCreateSSHCredentialsEntry
KeychainCredentialUpdate = KeychainCredentialUpdateSSHKeyPairEntry | KeychainCredentialUpdateSSHCredentialsEntry


class KeychainCredentialCreateArgs(BaseModel):
    keychain_credential_create: KeychainCredentialCreate


class KeychainCredentialCreateResult(BaseModel):
    result: SSHKeyPairEntry | SSHCredentialsEntry


class KeychainCredentialUpdateArgs(BaseModel):
    id: int
    keychain_credential_update: KeychainCredentialUpdate


class KeychainCredentialUpdateResult(BaseModel):
    result: SSHKeyPairEntry | SSHCredentialsEntry


class KeychainCredentialDeleteOptions(BaseModel):
    cascade: bool = False


class KeychainCredentialDeleteArgs(BaseModel):
    id: int
    options: KeychainCredentialDeleteOptions = KeychainCredentialDeleteOptions()


class KeychainCredentialDeleteResult(BaseModel):
    result: None


class KeychainCredentialUsedByArgs(BaseModel):
    id: int


class UsedKeychainCredential(BaseModel):
    title: str
    unbind_method: Literal["delete", "disable"]


class KeychainCredentialUsedByResult(BaseModel):
    result: list[UsedKeychainCredential]


class KeychainCredentialGenerateSshKeyPairArgs(BaseModel):
    pass


@single_argument_result
class KeychainCredentialGenerateSshKeyPairResult(BaseModel):
    private_key: LongString
    public_key: LongString


@single_argument_args("keychain_remote_ssh_host_key_scan")
class KeychainCredentialRemoteSshHostKeyScanArgs(BaseModel):
    host: NonEmptyString
    port: int = 22
    connect_timeout: int = 10


class KeychainCredentialRemoteSshHostKeyScanResult(BaseModel):
    result: LongString


class KeychainCredentialRemoteSSHSemiautomaticSetup(BaseModel):
    name: NonEmptyString
    url: HttpUrl
    verify_ssl: bool = True
    token: Secret[str | None] = None
    admin_username: str = "root"
    password: Secret[str | None] = None
    otp_token: Secret[str | None] = None
    username: str = "root"
    private_key: Secret[int]
    connect_timeout: int = 10
    sudo: bool = False


class KeychainCredentialRemoteSshSemiautomaticSetupArgs(BaseModel):
    data: KeychainCredentialRemoteSSHSemiautomaticSetup


class KeychainCredentialRemoteSshSemiautomaticSetupResult(BaseModel):
    result: SSHCredentialsEntry


class KeychainCredentialSetupSSHConnectionKeyNew(BaseModel):
    generate_key: Literal[True] = True
    name: NonEmptyString


class KeychainCredentialSetupSSHConnectionKeyExisting(BaseModel):
    generate_key: Literal[False] = False
    existing_key_id: int


class KeychainCredentialSetupSSHConnectionSemiAutomaticSetup(KeychainCredentialRemoteSSHSemiautomaticSetup):
    name: Excluded = excluded_field()
    private_key: Excluded = excluded_field()


class SetupSSHConnectionManualSetup(SSHCredentials):
    private_key: Excluded = excluded_field()


class SetupSSHConnectionManual(BaseModel):
    private_key: Annotated[
        Union[KeychainCredentialSetupSSHConnectionKeyNew, KeychainCredentialSetupSSHConnectionKeyExisting],
        Discriminator("generate_key"),
    ]
    connection_name: NonEmptyString
    setup_type: Literal["MANUAL"] = "MANUAL"
    manual_setup: SetupSSHConnectionManualSetup


class SetupSSHConnectionSemiautomatic(SetupSSHConnectionManual):
    setup_type: Literal["SEMI-AUTOMATIC"] = "SEMI-AUTOMATIC"
    semi_automatic_setup: KeychainCredentialSetupSSHConnectionSemiAutomaticSetup
    manual_setup: Excluded = excluded_field()


class KeychainCredentialSetupSshConnectionArgs(BaseModel):
    options: Annotated[
        Union[SetupSSHConnectionManual, SetupSSHConnectionSemiautomatic],
        Discriminator("setup_type"),
    ]


class KeychainCredentialSetupSshConnectionResult(BaseModel):
    result: SSHCredentialsEntry
