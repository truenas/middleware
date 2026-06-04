from typing import Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    NonEmptyString,
    excluded_field,
)

from .zfs_tier import TierInfo

__all__ = [
    "WebshareEntry", "WebshareUpdateArgs", "WebshareUpdate", "WebshareUpdateResult",
    "WebshareBindipChoicesArgs", "WebshareBindipChoicesResult",
    "SharingWebshareEntry", "SharingWebshareCreate", "SharingWebshareCreateArgs", "SharingWebshareCreateResult",
    "SharingWebshareUpdate", "SharingWebshareUpdateArgs", "SharingWebshareUpdateResult",
    "SharingWebshareDeleteArgs", "SharingWebshareDeleteResult",
]


class WebshareEntry(BaseModel):
    """TrueNAS Webshare server configuration. """
    id: int = Field(description="Unique identifier for the Webshare service configuration.")
    bindip: list[str] = Field(description="List of IP addresses used by the TrueNAS Webshare server.")
    search: bool = Field(description="Search indexing is enabled.")
    passkey: Literal["ENABLED", "DISABLED", "REQUIRED"] = Field(description="Passkey authentication mode.")
    groups: list[str] = Field(
        description="A list of AD/LDAP group names whose members will be granted access to Webshare.",
    )


class WebshareUpdate(WebshareEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class WebshareUpdateArgs(BaseModel):
    webshare_update: WebshareUpdate = Field(description="Updated webshare configuration data.")


class WebshareUpdateResult(BaseModel):
    result: WebshareEntry = Field(description="The updated Webshare service configuration.")


class WebshareBindipChoicesArgs(BaseModel):
    pass


class WebshareBindipChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="Available IP addresses that Webshare service can bind to.")


class SharingWebshareEntry(BaseModel):
    """Webshare share entry on the TrueNAS server. """
    id: int = Field(description="Unique identifier for this Webshare share.")
    name: NonEmptyString = Field(description="Webshare share name.")
    path: NonEmptyString = Field(
        description=(
            "Local server path to share by using the Webshare protocol. The path must start with `/mnt/` and must be in"
            " a ZFS pool."
        ),
    )
    dataset: str | None = Field(
        description="Dataset name component of the path (e.g., 'tank/webshare'). Null if path cannot be resolved.",
    )
    relative_path: str | None = Field(
        description=(
            "Relative path component within the dataset (e.g., 'subdir/data'). Null if path cannot be resolved."
        ),
    )
    enabled: bool = Field(default=True, description="If unset, the Webshare share is not available.")
    is_home_base: bool = Field(
        default=False,
        description=(
            "If set, this share is used as the base path for user home directories. Only one share can have this "
            "enabled."
        ),
    )
    locked: bool | None = Field(
        description=(
            "Read-only value indicating whether the share is located on a locked dataset.\n"
            "\n"
            "Returns:\n"
            "    - True: The share is in a locked dataset.\n"
            "    - False: The share is not in a locked dataset.\n"
            "    - None: Lock status is not available because path locking information was not requested."
        ),
    )
    tier: TierInfo | None = Field(
        default=None,
        description=(
            "Storage tier in which the share's underlying dataset is located. This field is read-only; configure the "
            "dataset's tier via `zfs.tier.dataset_set_tier`.\n"
            "\n"
            "NOTE: this is a licensed feature. Will be `null` if TrueNAS is unlicensed, if tiering is disabled, or if "
            "the pool has no SPECIAL vdev."
        ),
    )


class SharingWebshareCreate(SharingWebshareEntry):
    id: Excluded = excluded_field()
    dataset: Excluded = excluded_field()
    relative_path: Excluded = excluded_field()
    locked: Excluded = excluded_field()
    tier: Excluded = excluded_field()


class SharingWebshareCreateArgs(BaseModel):
    data: SharingWebshareCreate = Field(description="Webshare share configuration data for the new share.")


class SharingWebshareCreateResult(BaseModel):
    result: SharingWebshareEntry = Field(description="The created Webshare share configuration.")


class SharingWebshareUpdate(SharingWebshareCreate, metaclass=ForUpdateMetaclass):
    pass


class SharingWebshareUpdateArgs(BaseModel):
    id: int = Field(description="ID of the Webshare share to update.")
    data: SharingWebshareUpdate = Field(description="Updated Webshare share configuration data.")


class SharingWebshareUpdateResult(BaseModel):
    result: SharingWebshareEntry = Field(description="The updated Webshare share configuration.")


class SharingWebshareDeleteArgs(BaseModel):
    id: int = Field(description="ID of the Webshare share to delete.")


class SharingWebshareDeleteResult(BaseModel):
    result: None
