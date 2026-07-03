from __future__ import annotations

from typing import TYPE_CHECKING, Literal, overload

from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.api.current import (
    KeychainCredentialCreate,
    KeychainCredentialCreateArgs,
    KeychainCredentialCreateResult,
    KeychainCredentialDeleteArgs,
    KeychainCredentialDeleteOptions,
    KeychainCredentialDeleteResult,
    KeychainCredentialEntry,
    KeychainCredentialGenerateSshKeyPairArgs,
    KeychainCredentialGenerateSshKeyPairResult,
    KeychainCredentialRemoteSshHostKeyScanArgs,
    KeychainCredentialRemoteSshHostKeyScanResult,
    KeychainCredentialRemoteSSHSemiautomaticSetup,
    KeychainCredentialRemoteSshSemiautomaticSetupArgs,
    KeychainCredentialRemoteSshSemiautomaticSetupResult,
    KeychainCredentialSetupSshConnectionArgs,
    KeychainCredentialSetupSshConnectionResult,
    KeychainCredentialUpdate,
    KeychainCredentialUpdateArgs,
    KeychainCredentialUpdateResult,
    KeychainCredentialUsedByArgs,
    KeychainCredentialUsedByResult,
    SetupSSHConnectionManual,
    SetupSSHConnectionSemiautomatic,
    SSHCredentialsEntry,
    SSHKeyPair,
    SSHKeyPairEntry,
    UsedKeychainCredential,
)
from middlewared.service import GenericCRUDService
from middlewared.utils.types import AuditCallback

from .crud import KeychainCredentialServicePart
from .ssh_key import generate_ssh_key_pair, remote_ssh_host_key_scan
from .ssh_pair import (
    KeychainCredentialSSHPairArg,
    KeychainCredentialSSHPairArgs,
    KeychainCredentialSSHPairResult,
    KeychainCredentialSSHPairResultData,
    remote_ssh_semiautomatic_setup,
    setup_ssh_connection,
    ssh_pair,
)
from .used_by import get_used_by
from .utils import get_of_type

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("KeychainCredentialService",)


class KeychainCredentialGetOfTypeArgs(BaseModel):
    id: int
    type: Literal["SSH_KEY_PAIR", "SSH_CREDENTIALS"]


class KeychainCredentialGetOfTypeResult(BaseModel):
    result: SSHKeyPairEntry | SSHCredentialsEntry


class KeychainCredentialService(GenericCRUDService[KeychainCredentialEntry]):
    _svc_part: KeychainCredentialServicePart

    class Config:
        cli_namespace = "system.keychain_credential"
        role_prefix = "KEYCHAIN_CREDENTIAL"
        entry = KeychainCredentialEntry
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = KeychainCredentialServicePart(self.context)

    @api_method(
        KeychainCredentialCreateArgs,
        KeychainCredentialCreateResult,
        audit="Create Keychain Credential:",
        audit_extended=lambda data: data["name"],
        check_annotations=True,
    )
    async def do_create(self, data: KeychainCredentialCreate) -> KeychainCredentialEntry:
        """
        Create a Keychain Credential.
        """
        return await self._svc_part.do_create(data)

    @api_method(
        KeychainCredentialUpdateArgs,
        KeychainCredentialUpdateResult,
        audit="Update Keychain Credential:",
        audit_callback=True,
        check_annotations=True,
    )
    async def do_update(
        self,
        audit_callback: AuditCallback,
        id_: int,
        data: KeychainCredentialUpdate,
    ) -> KeychainCredentialEntry:
        """
        Update a Keychain Credential with specific ``id``.

        Please note that you can't change ``type``. You must specify full ``attributes`` value.
        """
        return await self._svc_part.do_update(audit_callback, id_, data)

    @api_method(
        KeychainCredentialDeleteArgs,
        KeychainCredentialDeleteResult,
        audit="Delete Keychain Credential:",
        audit_callback=True,
        check_annotations=True,
    )
    async def do_delete(
        self,
        audit_callback: AuditCallback,
        id_: int,
        options: KeychainCredentialDeleteOptions = KeychainCredentialDeleteOptions(),
    ) -> None:
        """
        Delete Keychain Credential with specific ``id``.
        """
        await self._svc_part.do_delete(audit_callback, id_, options)

    @api_method(
        KeychainCredentialUsedByArgs,
        KeychainCredentialUsedByResult,
        roles=["KEYCHAIN_CREDENTIAL_READ"],
        check_annotations=True,
    )
    async def used_by(self, id_: int) -> list[UsedKeychainCredential]:
        """
        Returns list of objects that use this credential.
        """
        return await get_used_by(self, id_)

    @overload
    async def get_of_type(self, id_: int, type_: Literal["SSH_KEY_PAIR"]) -> SSHKeyPairEntry: ...
    @overload
    async def get_of_type(self, id_: int, type_: Literal["SSH_CREDENTIALS"]) -> SSHCredentialsEntry: ...
    @api_method(
        KeychainCredentialGetOfTypeArgs,
        KeychainCredentialGetOfTypeResult,
        private=True,
        check_annotations=True,
    )
    async def get_of_type(
        self,
        id_: int,
        type_: Literal["SSH_KEY_PAIR", "SSH_CREDENTIALS"],
    ) -> SSHKeyPairEntry | SSHCredentialsEntry:
        return await get_of_type(self.context, id_, type_)

    @api_method(
        KeychainCredentialGenerateSshKeyPairArgs,
        KeychainCredentialGenerateSshKeyPairResult,
        roles=["KEYCHAIN_CREDENTIAL_WRITE"],
        check_annotations=True,
    )
    def generate_ssh_key_pair(self) -> SSHKeyPair:
        """
        Generate a public/private key pair (useful for ``SSH_KEY_PAIR`` type).
        """
        return generate_ssh_key_pair()

    @api_method(
        KeychainCredentialRemoteSshHostKeyScanArgs,
        KeychainCredentialRemoteSshHostKeyScanResult,
        roles=["KEYCHAIN_CREDENTIAL_WRITE"],
        check_annotations=True,
    )
    async def remote_ssh_host_key_scan(self, data: KeychainCredentialRemoteSshHostKeyScanArgs) -> str:
        """
        Discover a remote host key (useful for ``SSH_CREDENTIALS``).
        """
        return await remote_ssh_host_key_scan(data)

    @api_method(
        KeychainCredentialRemoteSshSemiautomaticSetupArgs,
        KeychainCredentialRemoteSshSemiautomaticSetupResult,
        roles=["KEYCHAIN_CREDENTIAL_WRITE"],
        audit="SSH Semi-automatic Setup:",
        audit_extended=lambda data: data["name"],
        check_annotations=True,
    )
    def remote_ssh_semiautomatic_setup(
        self,
        data: KeychainCredentialRemoteSSHSemiautomaticSetup,
    ) -> SSHCredentialsEntry:
        """
        Perform semi-automatic SSH connection setup with other TrueNAS machine.

        It creates an ``SSH_CREDENTIALS`` credential with specified ``name`` that can be used to connect to TrueNAS
        machine with specified ``url`` and temporary auth ``token``. Other TrueNAS machine adds ``private_key`` to
        allowed ``username``'s private keys. Other ``SSH_CREDENTIALS`` attributes such as ``connect_timeout`` can be
        specified as well.
        """
        return remote_ssh_semiautomatic_setup(self.context, data)

    @api_method(KeychainCredentialSSHPairArgs, KeychainCredentialSSHPairResult, private=True, check_annotations=True)
    def ssh_pair(self, data: KeychainCredentialSSHPairArg) -> KeychainCredentialSSHPairResultData:
        """
        Receives public key, storing it to accept SSH connection and return pertinent SSH data of this machine.
        """
        return ssh_pair(self.context, data)

    @api_method(
        KeychainCredentialSetupSshConnectionArgs,
        KeychainCredentialSetupSshConnectionResult,
        roles=["KEYCHAIN_CREDENTIAL_WRITE"],
        audit="Setup SSH Connection:",
        audit_extended=lambda options: options["connection_name"],
        check_annotations=True,
    )
    async def setup_ssh_connection(
        self,
        options: SetupSSHConnectionManual | SetupSSHConnectionSemiautomatic,
    ) -> SSHCredentialsEntry:
        """
        Create an SSH connection by performing the following steps:

        1. Generate an SSH key pair if required.
        2. Set up SSH credentials based on ``setup_type``.

        If step 2 fails, any SSH key pair generated in the process is removed.
        """
        return await setup_ssh_connection(self.context, options)
