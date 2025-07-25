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
    """SSH private key in OpenSSH format. `null` if only public key is provided."""
    public_key: LongString | None = None
    """Can be omitted and automatically derived from the private key."""


class SSHCredentials(BaseModel):
    host: str
    """SSH server hostname or IP address."""
    port: int = 22
    """SSH server port number."""
    username: str = "root"
    """SSH username for authentication."""
    private_key: int
    """Keychain Credential ID."""
    remote_host_key: str
    """Can be discovered with keychaincredential.remote_ssh_host_key_scan."""
    connect_timeout: int = 10
    """Connection timeout in seconds for SSH connections."""


class KeychainCredentialEntry(BaseModel, abc.ABC):
    id: int
    """Unique identifier for this keychain credential."""
    name: NonEmptyString
    """Distinguishes this Keychain Credential from others."""
    type: Literal["SSH_KEY_PAIR", "SSH_CREDENTIALS"]
    """Type of credential stored in the keychain.

    * `SSH_KEY_PAIR`: SSH public/private key pair
    * `SSH_CREDENTIALS`: SSH connection credentials including host and authentication
    """
    attributes: Secret[SSHKeyPair | SSHCredentials]
    """Credential-specific configuration and authentication data."""


class SSHKeyPairEntry(KeychainCredentialEntry):
    type: Literal["SSH_KEY_PAIR"]
    """Keychain credential type identifier for SSH key pairs."""
    attributes: Secret[SSHKeyPair]
    """SSH key pair attributes including public and private keys."""


class SSHCredentialsEntry(KeychainCredentialEntry):
    type: Literal["SSH_CREDENTIALS"]
    """Keychain credential type identifier for SSH connection credentials."""
    attributes: Secret[SSHCredentials]
    """SSH connection attributes including host, authentication, and connection settings."""


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
    """Credential configuration data for the new keychain entry."""


class KeychainCredentialCreateResult(BaseModel):
    result: SSHKeyPairEntry | SSHCredentialsEntry
    """The newly created keychain credential entry."""


class KeychainCredentialUpdateArgs(BaseModel):
    id: int
    """Unique identifier of the keychain credential to update."""
    keychain_credential_update: KeychainCredentialUpdate
    """Updated credential configuration data."""


class KeychainCredentialUpdateResult(BaseModel):
    result: SSHKeyPairEntry | SSHCredentialsEntry
    """The updated keychain credential entry."""


class KeychainCredentialDeleteOptions(BaseModel):
    cascade: bool = False
    """Whether to force deletion even if the credential is in use by other services."""


class KeychainCredentialDeleteArgs(BaseModel):
    id: int
    """Unique identifier of the keychain credential to delete."""
    options: KeychainCredentialDeleteOptions = KeychainCredentialDeleteOptions()
    """Options controlling the deletion behavior."""


class KeychainCredentialDeleteResult(BaseModel):
    result: None


class KeychainCredentialUsedByArgs(BaseModel):
    id: int
    """Unique identifier of the keychain credential to check usage for."""


class UsedKeychainCredential(BaseModel):
    title: str
    """Human-readable description of where the credential is being used."""
    unbind_method: Literal["delete", "disable"]
    """How to remove the credential dependency.

    * `delete`: Delete the dependent configuration
    * `disable`: Disable the dependent service or feature
    """


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
