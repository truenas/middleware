from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api.current import CloudSyncProvider, CloudSyncProviderTaskSchemaItem
from middlewared.plugins.cloud.crud import task_attributes
from middlewared.plugins.cloud.path import get_remote_path
from middlewared.plugins.cloud.rclone.remote.storjix import StorjIxError
from middlewared.plugins.cloud.remotes import REMOTES
from middlewared.service import CallError, ValidationError, ValidationErrors

from .rclone import ls

if TYPE_CHECKING:
    from middlewared.api.current import CloudSyncListDirectory

    from .crud import CloudSyncServicePart


OAUTH_URL = "https://www.truenas.com/oauth"


def list_directory(part: CloudSyncServicePart, cloud_sync: CloudSyncListDirectory) -> list[dict[str, Any]]:
    verrors = ValidationErrors()

    # `_basic_validate` normalizes `cloud_sync.attributes` in place (fills provider defaults).
    part._basic_validate(verrors, "cloud_sync", cloud_sync)

    verrors.check()

    credentials = part._get_credentials(cloud_sync.credentials)
    assert credentials is not None  # `_basic_validate` above already rejected invalid credentials

    remote = REMOTES[credentials.provider.type]

    path = get_remote_path(remote, cloud_sync.attributes.model_dump())

    return ls(part.middleware, credentials.provider, cloud_sync, path)


def list_buckets(part: CloudSyncServicePart, credentials_id: int) -> list[dict[str, Any]]:
    credentials = part._get_credentials(credentials_id)
    if not credentials:
        raise CallError("Invalid credentials")

    remote = REMOTES[credentials.provider.type]

    if not remote.buckets:
        raise CallError("This provider does not use buckets")

    if remote.custom_list_buckets:
        return [
            {
                "Path": bucket["name"],
                "Name": bucket["name"],
                "Size": -1,
                "MimeType": "inode/directory",
                "ModTime": bucket["time"],
                "IsDir": True,
                "IsBucket": True,
                "Enabled": bucket["enabled"],
            }
            for bucket in remote.list_buckets(credentials.provider)
        ]

    return ls(part.middleware, credentials.provider, None, "")


def create_bucket(part: CloudSyncServicePart, credentials_id: int, name: str) -> None:
    credentials = part._get_credentials(credentials_id)
    if not credentials:
        raise CallError("Invalid credentials")

    remote = REMOTES[credentials.provider.type]

    if not remote.can_create_bucket:
        raise CallError("This provider can't create buckets")

    try:
        remote.create_bucket(credentials.provider, name)
    except StorjIxError as e:
        raise ValidationError("cloudsync.create_bucket", e.errmsg, e.errno)


def providers(part: CloudSyncServicePart) -> list[CloudSyncProvider]:
    return sorted(
        [
            CloudSyncProvider(
                name=provider.name,
                title=provider.title,
                credentials_oauth=(
                    f"{OAUTH_URL}/{(provider.credentials_oauth_name or provider.name.lower())}"
                    if provider.credentials_oauth else None
                ),
                buckets=provider.buckets,
                bucket_title=provider.bucket_title,
                task_schema=[
                    CloudSyncProviderTaskSchemaItem(property=attribute)
                    for attribute in task_attributes(provider)
                ],
            )
            for provider in REMOTES.values()
        ],
        key=lambda provider: provider.title.lower()
    )
