import abc
from typing import Annotated, Literal, Union

from pydantic import Discriminator, Field, Secret

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    HttpUrl,
    LongString,
    NonEmptyString,
    excluded_field,
    single_argument_args,
)

__all__ = ["KeychainCredentialEntry",
           "SSHKeyPair", "SSHKeyPairEntry", "SSHCredentials", "SSHCredentialsEntry",
           "KeychainCredentialCreateSSHCredentialsEntry", "KeychainCredentialCreateSSHKeyPairEntry",
           "KeychainCredentialCreate", "KeychainCredentialUpdate",
           "KeychainCredentialCreateArgs", "KeychainCredentialCreateResult",
           "KeychainCredentialUpdateArgs", "KeychainCredentialUpdateResult",
           "KeychainCredentialDeleteOptions", "KeychainCredentialDeleteArgs", "KeychainCredentialDeleteResult",
           "KeychainCredentialUsedByArgs", "KeychainCredentialUsedByResult", "UsedKeychainCredential",
           "KeychainCredentialGenerateSshKeyPairArgs", "KeychainCredentialGenerateSshKeyPairResult",
           "KeychainCredentialRemoteSshHostKeyScanArgs", "KeychainCredentialRemoteSshHostKeyScanResult",
           "KeychainCredentialRemoteSSHSemiautomaticSetup",
           "KeychainCredentialRemoteSshSemiautomaticSetupArgs", "KeychainCredentialRemoteSshSemiautomaticSetupResult",
           "SetupSSHConnectionManual", "SetupSSHConnectionSemiautomatic",
           "KeychainCredentialSetupSshConnectionArgs", "KeychainCredentialSetupSshConnectionResult"]


class SSHKeyPair(BaseModel):
    """At least one of the two keys must be provided on creation."""
    private_key: LongString | None = Field(
        default=None,
        description="SSH private key in OpenSSH format. `null` if only public key is provided.",
    )
    public_key: LongString | None = Field(
        default=None,
        description="Can be omitted and automatically derived from the private key.",
    )


class SSHCredentials(BaseModel):
    host: str = Field(description="SSH server hostname or IP address.")
    port: int = Field(default=22, description="SSH server port number.")
    username: str = Field(default="root", description="SSH username for authentication.")
    private_key: int = Field(description="Keychain Credential ID.")
    remote_host_key: str = Field(description="Can be discovered with keychaincredential.remote_ssh_host_key_scan.")
    connect_timeout: int = Field(default=10, description="Connection timeout in seconds for SSH connections.")


class KeychainCredentialEntry(BaseModel, abc.ABC):
    id: int = Field(description="Unique identifier for this keychain credential.")
    name: NonEmptyString = Field(description="Distinguishes this Keychain Credential from others.")
    type: Literal["SSH_KEY_PAIR", "SSH_CREDENTIALS"] = Field(
        description=(
            "Type of credential stored in the keychain.\n"
            "\n"
            "* `SSH_KEY_PAIR`: SSH public/private key pair\n"
            "* `SSH_CREDENTIALS`: SSH connection credentials including host and authentication"
        ),
    )
    attributes: Secret[SSHKeyPair | SSHCredentials] = Field(
        description="Credential-specific configuration and authentication data.",
    )


class SSHKeyPairEntry(KeychainCredentialEntry):
    type: Literal["SSH_KEY_PAIR"] = Field(description="Keychain credential type identifier for SSH key pairs.")
    attributes: Secret[SSHKeyPair] = Field(description="SSH key pair attributes including public and private keys.")


class SSHCredentialsEntry(KeychainCredentialEntry):
    type: Literal["SSH_CREDENTIALS"] = Field(
        description="Keychain credential type identifier for SSH connection credentials.",
    )
    attributes: Secret[SSHCredentials] = Field(
        description="SSH connection attributes including host, authentication, and connection settings.",
    )


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
    keychain_credential_create: KeychainCredentialCreate = Field(
        description="Credential configuration data for the new keychain entry.",
    )


class KeychainCredentialCreateResult(BaseModel):
    result: KeychainCredentialEntry = Field(description="The newly created keychain credential entry.")


class KeychainCredentialUpdateArgs(BaseModel):
    id: int = Field(description="Unique identifier of the keychain credential to update.")
    keychain_credential_update: KeychainCredentialUpdate = Field(description="Updated credential configuration data.")


class KeychainCredentialUpdateResult(BaseModel):
    result: KeychainCredentialEntry = Field(description="The updated keychain credential entry.")


class KeychainCredentialDeleteOptions(BaseModel):
    cascade: bool = Field(
        default=False,
        description="Whether to force deletion even if the credential is in use by other services.",
    )


class KeychainCredentialDeleteArgs(BaseModel):
    id: int = Field(description="Unique identifier of the keychain credential to delete.")
    options: KeychainCredentialDeleteOptions = Field(
        default=KeychainCredentialDeleteOptions(),
        description="Options controlling the deletion behavior.",
    )


class KeychainCredentialDeleteResult(BaseModel):
    result: None


class KeychainCredentialUsedByArgs(BaseModel):
    id: int = Field(description="Unique identifier of the keychain credential to check usage for.")


class UsedKeychainCredential(BaseModel):
    title: str = Field(description="Human-readable description of where the credential is being used.")
    unbind_method: Literal["delete", "disable"] = Field(
        description=(
            "How to remove the credential dependency.\n"
            "\n"
            "* `delete`: Delete the dependent configuration\n"
            "* `disable`: Disable the dependent service or feature"
        ),
    )


class KeychainCredentialUsedByResult(BaseModel):
    result: list[UsedKeychainCredential] = Field(
        description="Array of services or features using this keychain credential.",
    )


class KeychainCredentialGenerateSshKeyPairArgs(BaseModel):
    pass


class KeychainCredentialGenerateSshKeyPairResult(BaseModel):
    result: SSHKeyPair


@single_argument_args("keychain_remote_ssh_host_key_scan")
class KeychainCredentialRemoteSshHostKeyScanArgs(BaseModel):
    host: NonEmptyString = Field(description="Hostname or IP address of the remote SSH server to scan.")
    port: int = Field(default=22, description="TCP port number for the SSH connection.")
    connect_timeout: int = Field(default=10, description="Connection timeout in seconds.")


class KeychainCredentialRemoteSshHostKeyScanResult(BaseModel):
    result: LongString = Field(description="SSH host public key retrieved from the remote server.")


class KeychainCredentialRemoteSSHSemiautomaticSetup(BaseModel):
    name: NonEmptyString = Field(description="Name for the SSH connection credential.")
    url: HttpUrl = Field(description="URL of the remote TrueNAS system for semi-automatic setup.")
    verify_ssl: bool = Field(
        default=True,
        description="Whether to verify SSL certificates when connecting to the remote system.",
    )
    token: Secret[str | None] = Field(
        default=None,
        validate_default=True,
        description="API token for authentication with the remote system or `null`.",
    )
    admin_username: str = Field(default="root", description="Administrative username for the remote system.")
    password: Secret[str | None] = Field(
        default=None,
        validate_default=True,
        description="Password for the administrative user or `null`.",
    )
    otp_token: Secret[str | None] = Field(
        default=None,
        validate_default=True,
        description="One-time password token for 2FA authentication or `null`.",
    )
    username: str = Field(default="root", description="Username for the SSH connection.")
    private_key: Secret[int] = Field(
        description="ID of the existing private key credential to use for SSH authentication.",
    )
    connect_timeout: int = Field(default=10, description="SSH connection timeout in seconds.")
    sudo: bool = Field(default=False, description="Whether the SSH user should use sudo for elevated privileges.")


class KeychainCredentialRemoteSshSemiautomaticSetupArgs(BaseModel):
    data: KeychainCredentialRemoteSSHSemiautomaticSetup = Field(
        description="Configuration data for semi-automatic SSH credential setup.",
    )


class KeychainCredentialRemoteSshSemiautomaticSetupResult(BaseModel):
    result: SSHCredentialsEntry = Field(description="The created SSH credential configuration.")


class KeychainCredentialSetupSSHConnectionKeyNew(BaseModel):
    generate_key: Literal[True] = Field(default=True, description="Indicates a new SSH key pair should be generated.")
    name: NonEmptyString = Field(description="Name for the new SSH key credential.")


class KeychainCredentialSetupSSHConnectionKeyExisting(BaseModel):
    generate_key: Literal[False] = Field(default=False, description="Indicates an existing SSH key should be used.")
    existing_key_id: int = Field(description="ID of the existing SSH private key credential to use.")


class KeychainCredentialSetupSSHConnectionSemiAutomaticSetup(KeychainCredentialRemoteSSHSemiautomaticSetup):
    name: Excluded = excluded_field()
    private_key: Excluded = excluded_field()


class SetupSSHConnectionManualSetup(SSHCredentials):
    private_key: Excluded = excluded_field()


class SetupSSHConnectionManual(BaseModel):
    private_key: Annotated[
        Union[KeychainCredentialSetupSSHConnectionKeyNew, KeychainCredentialSetupSSHConnectionKeyExisting],
        Discriminator("generate_key"),
    ] = Field(description="SSH private key configuration (new or existing).")
    connection_name: NonEmptyString = Field(description="Name for the SSH connection credential.")
    setup_type: Literal["MANUAL"] = Field(default="MANUAL", description="Setup method for the SSH connection.")
    manual_setup: SetupSSHConnectionManualSetup = Field(description="Manual SSH connection configuration parameters.")


class SetupSSHConnectionSemiautomatic(SetupSSHConnectionManual):
    setup_type: Literal["SEMI-AUTOMATIC"] = Field(
        default="SEMI-AUTOMATIC",
        description="Setup method for the SSH connection.",
    )
    semi_automatic_setup: KeychainCredentialSetupSSHConnectionSemiAutomaticSetup = Field(
        description="Semi-automatic SSH connection configuration parameters.",
    )
    manual_setup: Excluded = excluded_field()


class KeychainCredentialSetupSshConnectionArgs(BaseModel):
    options: Annotated[
        Union[SetupSSHConnectionManual, SetupSSHConnectionSemiautomatic],
        Discriminator("setup_type"),
    ] = Field(description="SSH connection setup configuration (manual or semi-automatic).")


class KeychainCredentialSetupSshConnectionResult(BaseModel):
    result: SSHCredentialsEntry = Field(description="The created SSH connection credential.")
