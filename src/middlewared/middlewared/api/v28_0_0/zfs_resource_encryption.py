from typing import Annotated, Literal

from pydantic import Field, Secret

from middlewared.api.base import BaseModel, NonEmptyString

__all__ = (
    "ZFSResourceEncryptionChangeKeyArgs",
    "ZFSResourceEncryptionChangeKeyArgsData",
    "ZFSResourceEncryptionChangeKeyResult",
    "ZFSResourceEncryptionExportKeyArgs",
    "ZFSResourceEncryptionExportKeyArgsData",
    "ZFSResourceEncryptionExportKeyResult",
    "ZFSResourceEncryptionExportKeysArgs",
    "ZFSResourceEncryptionExportKeysArgsData",
    "ZFSResourceEncryptionExportKeysResult",
    "ZFSResourceEncryptionExportReplicationKeysArgs",
    "ZFSResourceEncryptionExportReplicationKeysArgsData",
    "ZFSResourceEncryptionExportReplicationKeysResult",
    "ZFSResourceEncryptionInheritArgs",
    "ZFSResourceEncryptionInheritArgsData",
    "ZFSResourceEncryptionInheritResult",
    "ZFSResourceEncryptionKeyFormat",
    "ZFSResourceEncryptionLockArgs",
    "ZFSResourceEncryptionLockArgsData",
    "ZFSResourceEncryptionLockResult",
    "ZFSResourceEncryptionUnlockArgs",
    "ZFSResourceEncryptionUnlockArgsData",
    "ZFSResourceEncryptionUnlockEntry",
    "ZFSResourceEncryptionUnlockFailure",
    "ZFSResourceEncryptionUnlockKey",
    "ZFSResourceEncryptionUnlockResult",
    "ZFSResourceEncryptionUnlockSummaryArgs",
    "ZFSResourceEncryptionUnlockSummaryArgsData",
    "ZFSResourceEncryptionUnlockSummaryEntry",
    "ZFSResourceEncryptionUnlockSummaryKey",
    "ZFSResourceEncryptionUnlockSummaryResult",
)

ZFSResourceEncryptionKeyFormat = Literal["hex", "raw", "passphrase"]
HEX_KEY = Annotated[str, Field(min_length=64, max_length=64)]
CHANGE_KEY_HEX_KEY = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")]


class ZFSResourceEncryptionLockArgsData(BaseModel):
    path: NonEmptyString = Field(
        description="Path of the encryption root to lock. Only roots encrypted with a passphrase can be locked.",
    )
    force_unmount: bool = Field(
        default=False,
        description="Forcibly unmount the resource and its descendants even if they are busy.",
    )


class ZFSResourceEncryptionLockArgs(BaseModel):
    data: ZFSResourceEncryptionLockArgsData = Field(description="Lock parameters.")


class ZFSResourceEncryptionLockResult(BaseModel):
    result: None = Field(description="Returns `null` once the resource is locked.")


class ZFSResourceEncryptionUnlockSummaryKey(BaseModel):
    path: NonEmptyString = Field(description="Path of the encryption root the key or passphrase belongs to.")
    key: Secret[HEX_KEY | None] = Field(
        default=None,
        description="A 64-character hex-encoded key for `path`. Must not be combined with `passphrase`.",
    )
    passphrase: Secret[NonEmptyString | None] = Field(
        default=None,
        description="The passphrase for `path`. Must not be combined with `key`.",
    )
    force: bool = Field(
        default=False,
        description=(
            "Rename whatever already occupies the mount path of `path` instead of failing because it exists and is "
            "not empty."
        ),
    )


class ZFSResourceEncryptionUnlockKey(ZFSResourceEncryptionUnlockSummaryKey):
    recursive: bool = Field(
        default=False,
        description="Also try this key or passphrase on locked encryption roots below `path` that have none supplied.",
    )


class ZFSResourceEncryptionUnlockArgsData(BaseModel):
    path: NonEmptyString = Field(
        description=(
            "Path of the encryption root to unlock. A pool root that is not itself encrypted is accepted when "
            "`recursive` is set, which unlocks the encrypted roots below it."
        ),
    )
    recursive: bool = Field(default=False, description="Also unlock the locked encryption roots below `path`.")
    force: bool = Field(
        default=False,
        description=(
            "Rename whatever already occupies a mount path instead of failing because it exists and is not empty. "
            "Applies to every resource being unlocked; `keys.X.force` applies to a single one."
        ),
    )
    key_file: bool = Field(
        default=False,
        description=(
            "Read keys from a JSON file uploaded to the input pipe, in the format written by "
            "`zfs.resource.encryption.export_keys`."
        ),
    )
    keys: list[ZFSResourceEncryptionUnlockKey] = Field(
        default=[],
        description="Keys or passphrases for individual encryption roots.",
    )
    start_attachments: bool = Field(
        default=True,
        description=(
            "Start the services, shares and other consumers of the unlocked resources once they are mounted. "
            "The system keeps no record of resources unlocked without their attachments, so disable this only "
            "when the caller restarts services itself."
        ),
    )


class ZFSResourceEncryptionUnlockArgs(BaseModel):
    data: ZFSResourceEncryptionUnlockArgsData = Field(description="Unlock parameters.")


class ZFSResourceEncryptionUnlockFailure(BaseModel):
    error: str | None = Field(description="Why the resource could not be unlocked.")
    skipped: list[str] = Field(description="Paths below the failed resource that were not attempted because of it.")


class ZFSResourceEncryptionUnlockEntry(BaseModel):
    unlocked: list[str] = Field(description="Paths of the resources that were unlocked and mounted.")
    failed: dict[str, ZFSResourceEncryptionUnlockFailure] = Field(
        description="Resources that could not be unlocked, keyed by path.",
    )


class ZFSResourceEncryptionUnlockResult(BaseModel):
    result: ZFSResourceEncryptionUnlockEntry = Field(description="Outcome of the unlock.")


class ZFSResourceEncryptionUnlockSummaryArgsData(BaseModel):
    path: NonEmptyString = Field(description="Path whose encryption roots, including itself, are summarized.")
    force: bool = Field(
        default=False,
        description="Assume an occupied mount path would be renamed, as `force` does for an unlock.",
    )
    key_file: bool = Field(
        default=False,
        description=(
            "Read keys from a JSON file uploaded to the input pipe, in the format written by "
            "`zfs.resource.encryption.export_keys`."
        ),
    )
    keys: list[ZFSResourceEncryptionUnlockSummaryKey] = Field(
        default=[],
        description="Keys or passphrases to check for individual encryption roots.",
    )


class ZFSResourceEncryptionUnlockSummaryArgs(BaseModel):
    data: ZFSResourceEncryptionUnlockSummaryArgsData = Field(description="Unlock summary parameters.")


class ZFSResourceEncryptionUnlockSummaryEntry(BaseModel):
    path: str = Field(description="Path of the encryption root.")
    key_format: ZFSResourceEncryptionKeyFormat = Field(description="Format of the encryption root's key.")
    key_present_in_database: bool = Field(description="Whether the system has a stored key for the encryption root.")
    valid_key: bool = Field(description="Whether the supplied or stored key opens the encryption root.")
    locked: bool = Field(description="Whether the encryption root is currently locked.")
    unlock_error: str | None = Field(description="Why an unlock would fail, or `null` if it would succeed.")
    unlock_successful: bool = Field(description="Whether an unlock with the same parameters would succeed.")


class ZFSResourceEncryptionUnlockSummaryResult(BaseModel):
    result: list[ZFSResourceEncryptionUnlockSummaryEntry] = Field(
        description="One entry per encryption root, parents before their descendants.",
    )


class ZFSResourceEncryptionExportKeyArgsData(BaseModel):
    path: NonEmptyString = Field(description="Path of the encryption root whose stored key is exported.")
    download: bool = Field(
        default=False,
        description=(
            "Write the key to the output pipe as a JSON file usable with `key_file` when unlocking, instead of "
            "returning it."
        ),
    )


class ZFSResourceEncryptionExportKeyArgs(BaseModel):
    data: ZFSResourceEncryptionExportKeyArgsData = Field(description="Export key parameters.")


class ZFSResourceEncryptionExportKeyResult(BaseModel):
    result: Secret[str | None] = Field(description="The stored key, or `null` when `download` is set.")


class ZFSResourceEncryptionExportKeysArgsData(BaseModel):
    path: NonEmptyString = Field(description="Path whose stored keys, and those of its descendants, are exported.")


class ZFSResourceEncryptionExportKeysArgs(BaseModel):
    data: ZFSResourceEncryptionExportKeysArgsData = Field(description="Export keys parameters.")


class ZFSResourceEncryptionExportKeysResult(BaseModel):
    result: None = Field(description="Returns `null` once the keys are written to the output pipe.")


class ZFSResourceEncryptionExportReplicationKeysArgsData(BaseModel):
    id: int = Field(description="ID of the push replication task whose source keys are exported.")


class ZFSResourceEncryptionExportReplicationKeysArgs(BaseModel):
    data: ZFSResourceEncryptionExportReplicationKeysArgsData = Field(
        description="Export replication keys parameters.",
    )


class ZFSResourceEncryptionExportReplicationKeysResult(BaseModel):
    result: None = Field(description="Returns `null` once the keys are written to the output pipe.")


class ZFSResourceEncryptionChangeKeyArgsData(BaseModel):
    """Exactly one of `key`, `passphrase`, `generate_key` or `key_file` must be provided."""

    path: NonEmptyString = Field(description="Path of the unlocked encryption root whose key is changed.")
    generate_key: bool = Field(default=False, description="Generate a new random 64-character hex key.")
    key_file: bool = Field(
        default=False,
        description="Read a 64-character hex key from the input pipe.",
    )
    pbkdf2iters: int = Field(
        default=1_300_000,
        ge=1_300_000,
        description=(
            "Number of PBKDF2 iterations for key derivation from the passphrase. Only meaningful together with "
            "`passphrase`. Higher values improve resistance to brute force attacks but increase unlock time."
        ),
    )
    passphrase: Secret[Annotated[str, Field(min_length=8, max_length=512)] | None] = Field(
        default=None,
        description="A new passphrase of 8 to 512 characters. Passphrases are never stored by the system.",
    )
    key: Secret[CHANGE_KEY_HEX_KEY | None] = Field(
        default=None, description="A new key of exactly 64 hexadecimal characters."
    )


class ZFSResourceEncryptionChangeKeyArgs(BaseModel):
    data: ZFSResourceEncryptionChangeKeyArgsData = Field(description="Change key parameters.")


class ZFSResourceEncryptionChangeKeyResult(BaseModel):
    result: None = Field(description="Returns `null` once the key is changed.")


class ZFSResourceEncryptionInheritArgsData(BaseModel):
    path: NonEmptyString = Field(
        description="Path of the unlocked encryption root that gives up its own key and joins its parent's.",
    )


class ZFSResourceEncryptionInheritArgs(BaseModel):
    data: ZFSResourceEncryptionInheritArgsData = Field(description="Inherit parameters.")


class ZFSResourceEncryptionInheritResult(BaseModel):
    result: None = Field(description="Returns `null` once the encryption root is inherited.")
