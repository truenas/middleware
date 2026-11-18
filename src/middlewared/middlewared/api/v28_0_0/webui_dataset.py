from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel

from .zfs_resource_crud import ZFSPropertiesEntry
from .zfs_tier import TierInfo

__all__ = (
    "WebUIDatasetDetailsArgs",
    "WebUIDatasetDetailsResult",
    "WebUIDatasetDetailsEntry",
    "WebUIDatasetConsumers",
    "WebUIDatasetTasks",
    "WebUIDatasetSMBShare",
    "WebUIDatasetNFSShare",
    "WebUIDatasetWebshareShare",
    "WebUIDatasetISCSIExtent",
    "WebUIDatasetNVMetNamespace",
    "WebUIDatasetVM",
    "WebUIDatasetContainer",
    "WebUIDatasetApp",
)


class WebUIDatasetSMBShare(BaseModel):
    enabled: bool = Field(description="Whether the SMB share is enabled.")
    path: str = Field(description="Path of the SMB share.")
    share_name: str = Field(description="Name of the SMB share.")


class WebUIDatasetNFSShare(BaseModel):
    enabled: bool = Field(description="Whether the NFS share is enabled.")
    path: str = Field(description="Path of the NFS share.")


class WebUIDatasetWebshareShare(BaseModel):
    enabled: bool = Field(description="Whether the WebShare is enabled.")
    path: str = Field(description="Path of the WebShare.")
    share_name: str = Field(description="Name of the WebShare.")


class WebUIDatasetISCSIExtent(BaseModel):
    enabled: bool = Field(description="Whether the iSCSI extent is enabled.")
    type: Literal["DISK", "FILE"] = Field(
        description="Whether the extent is the zvol itself or a file stored on the dataset."
    )
    path: str = Field(description="Device path of a zvol extent or file path of a file extent.")


class WebUIDatasetNVMetNamespace(BaseModel):
    enabled: bool = Field(description="Whether the NVMe-oF namespace is enabled.")
    type: Literal["ZVOL", "FILE"] = Field(
        description="Whether the namespace is the zvol itself or a file stored on the dataset."
    )
    path: str = Field(description="Device path of a zvol namespace or file path of a file namespace.")


class WebUIDatasetVM(BaseModel):
    name: str = Field(description="Name of the virtual machine.")
    path: str = Field(description="Path of the virtual machine disk that uses the dataset.")


class WebUIDatasetContainer(BaseModel):
    name: str = Field(description="Name of the container.")
    path: str = Field(description="Host path mounted into the container.")


class WebUIDatasetApp(BaseModel):
    name: str = Field(description="Name of the app.")
    path: str = Field(description="Host path the app mounts.")


class WebUIDatasetConsumers(BaseModel):
    smb: list[WebUIDatasetSMBShare] | None = Field(
        description="SMB shares of the dataset, or `null` unless the caller may call `sharing.smb.query`."
    )
    nfs: list[WebUIDatasetNFSShare] | None = Field(
        description="NFS shares of the dataset, or `null` unless the caller may call `sharing.nfs.query`."
    )
    webshare: list[WebUIDatasetWebshareShare] | None = Field(
        description="WebShares of the dataset, or `null` unless the caller may call `sharing.webshare.query`."
    )
    iscsi: list[WebUIDatasetISCSIExtent] | None = Field(
        description=(
            "iSCSI extents of the dataset that are mapped to a target with a portal group, or `null` unless the "
            "caller may call `iscsi.extent.query`, `iscsi.target.query` and `iscsi.targetextent.query`."
        )
    )
    nvmet: list[WebUIDatasetNVMetNamespace] | None = Field(
        description="NVMe-oF namespaces of the dataset, or `null` unless the caller may call `nvmet.namespace.query`."
    )
    vms: list[WebUIDatasetVM] | None = Field(
        description=(
            "Virtual machine disks that use the dataset, or `null` unless the caller may call `vm.query` and "
            "`vm.device.query`."
        )
    )
    containers: list[WebUIDatasetContainer] | None = Field(
        description=(
            "Container filesystem devices that use the dataset, or `null` unless the caller may call "
            "`container.query` and `container.device.query`."
        )
    )
    apps: list[WebUIDatasetApp] | None = Field(
        description="Running apps that mount a path on the dataset, or `null` unless the caller may call `app.query`."
    )


class WebUIDatasetTasks(BaseModel):
    snapshot: int | None = Field(
        description=(
            "Number of periodic snapshot tasks of the dataset, or `null` unless the caller may call "
            "`pool.snapshottask.query`."
        )
    )
    replication: int | None = Field(
        description=(
            "Number of push replication tasks that use the dataset as a source, or `null` unless the caller may "
            "call `replication.query`."
        )
    )
    cloudsync: int | None = Field(
        description=(
            "Number of push cloud sync tasks whose path contains the dataset, or `null` unless the caller may call "
            "`cloudsync.query`."
        )
    )
    rsync: int | None = Field(
        description=(
            "Number of push rsync tasks whose path contains the dataset, or `null` unless the caller may call "
            "`rsynctask.query`."
        )
    )


class WebUIDatasetDetailsEntry(BaseModel):
    id: str = Field(description="Dataset name, used as its identifier.")
    name: str = Field(description="Name of the dataset.")
    pool: str = Field(description="Name of the pool that holds the dataset.")
    type: Literal["FILESYSTEM", "VOLUME"] = Field(description="Type of the dataset.")
    createtxg: int = Field(description="Transaction group in which the dataset was created.")
    guid: int = Field(description="Globally unique identifier of the dataset.")
    properties: ZFSPropertiesEntry = Field(
        description="ZFS properties of the dataset, as returned by `zfs.resource.list`."
    )
    user_properties: dict[str, str] = Field(
        description="ZFS user properties of the dataset, as returned by `zfs.resource.list`."
    )
    tier: TierInfo | None = Field(
        description=(
            "Storage tier of a filesystem, or `null` for a volume, when ZFS tiering is disabled, when the pool has "
            "no special vdev, or when the dataset uses deduplication."
        )
    )
    snapshot_count: int | None = Field(
        description=(
            "Number of snapshots of the dataset, or `null` unless the caller may call `zfs.resource.snapshot.count`."
        )
    )
    thick_provisioned: bool | None = Field(
        description="Whether a zvol has space reserved for it, or `null` for a filesystem."
    )
    consumers: WebUIDatasetConsumers = Field(
        description="Shares, virtual machines, containers and apps that use the dataset."
    )
    tasks: WebUIDatasetTasks = Field(description="Data protection tasks that cover the dataset.")


class WebUIDatasetDetailsArgs(BaseModel):
    pass


class WebUIDatasetDetailsResult(BaseModel):
    result: list[WebUIDatasetDetailsEntry] = Field(
        description=(
            "Every dataset outside the system's internal datasets, each placed after its parent with siblings "
            "ordered by name."
        )
    )
