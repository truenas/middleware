from typing import Literal

from middlewared.api.base import (
    BaseModel,
    excluded_field,
    Excluded,
    ForUpdateMetaclass,
    NonEmptyString,
)

__all__ = [
    "WebshareEntry", "WebshareUpdateArgs", "WebshareUpdate", "WebshareUpdateResult",
    "SharingWebshareEntry", "SharingWebshareCreate", "SharingWebshareCreateArgs", "SharingWebshareCreateResult",
    "SharingWebshareUpdate", "SharingWebshareUpdateArgs", "SharingWebshareUpdateResult",
    "SharingWebshareDeleteArgs", "SharingWebshareDeleteResult",
]


class WebshareEntry(BaseModel):
    """TrueNAS Webshare server configuration. """
    id: int
    """Unique identifier for the Webshare service configuration."""
    search: bool
    """Search indexing is enabled."""
    passkey: Literal["ENABLED", "DISABLED", "REQUIRED"]
    """Passkey authentication mode."""


class WebshareUpdate(WebshareEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class WebshareUpdateArgs(BaseModel):
    webshare_update: WebshareUpdate
    """Updated webshare configuration data."""


class WebshareUpdateResult(BaseModel):
    result: WebshareEntry
    """The updated Webshare service configuration."""


class SharingWebshareEntry(BaseModel):
    """Webshare share entry on the TrueNAS server. """
    id: int
    """Unique identifier for this Webshare share."""
    name: NonEmptyString
    """Webshare share name."""
    path: NonEmptyString
    """Local server path to share by using the Webshare protocol. The path must start with `/mnt/` and must be in a \
    ZFS pool."""
    dataset: str | None = None
    """Dataset name component of the path (e.g., 'tank/webshare'). Null if path cannot be resolved."""
    relative_path: str | None = None
    """Relative path component within the dataset (e.g., 'subdir/data'). Null if path cannot be resolved."""
    enabled: bool = True
    """If unset, the Webshare share is not available."""
    is_home_base: bool = False
    """If set, this share is used as the base path for user home directories. Only one share can have this enabled."""
    locked: bool | None
    """Read-only value indicating whether the share is located on a locked dataset.

    Returns:
        - True: The share is in a locked dataset.
        - False: The share is not in a locked dataset.
        - None: Lock status is not available because path locking information was not requested.
    """


class SharingWebshareCreate(SharingWebshareEntry):
    id: Excluded = excluded_field()
    dataset: Excluded = excluded_field()
    relative_path: Excluded = excluded_field()
    locked: Excluded = excluded_field()


class SharingWebshareCreateArgs(BaseModel):
    data: SharingWebshareCreate
    """Webshare share configuration data for the new share."""


class SharingWebshareCreateResult(BaseModel):
    result: SharingWebshareEntry
    """The created Webshare share configuration."""


class SharingWebshareUpdate(SharingWebshareCreate, metaclass=ForUpdateMetaclass):
    pass


class SharingWebshareUpdateArgs(BaseModel):
    id: int
    """ID of the Webshare share to update."""
    data: SharingWebshareUpdate
    """Updated Webshare share configuration data."""


class SharingWebshareUpdateResult(BaseModel):
    result: SharingWebshareEntry
    """The updated Webshare share configuration."""


class SharingWebshareDeleteArgs(BaseModel):
    id: int
    """ID of the Webshare share to delete."""


class SharingWebshareDeleteResult(BaseModel):
    result: None
