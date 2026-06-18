from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    NonEmptyString,
    TcpPort,
    exclude_tcp_ports,
    excluded_field,
    single_argument_args,
)

from .zfs_tier import TierInfo

__all__ = [
    "NFSGetNfs3ClientsEntry",
    "NFSGetNfs4ClientsEntry",
    "NFSEntry",
    "NFSBindipChoicesArgs",
    "NFSBindipChoicesResult",
    "NFSClientCountArgs",
    "NFSClientCountResult",
    "SharingNFSEntry",
    "SharingNFSCreateArgs",
    "SharingNFSCreateResult",
    "SharingNFSUpdateArgs",
    "SharingNFSUpdateResult",
    "SharingNFSDeleteArgs",
    "SharingNFSDeleteResult",
    "NFSUpdateArgs",
    "NFSUpdateResult",
]

NFS_protocols = Literal["NFSV3", "NFSV4"]
NFS_RDMA_DEFAULT_PORT = 20049
EXCLUDED_PORTS = [NFS_RDMA_DEFAULT_PORT]
NfsTcpPort: TypeAlias = Annotated[
    TcpPort | None, AfterValidator(exclude_tcp_ports(EXCLUDED_PORTS))
]


class NFSGetNfs3ClientsEntry(BaseModel):
    ip: str = Field(description="IP address of the NFSv3 client.")
    export: str = Field(description="NFS export path being accessed by the client.")


class NFSGetNfs4ClientsEntry(BaseModel):
    id: str = Field(description="Unique identifier for the NFSv4 client.")
    info: dict = Field(description="Client information including connection details and capabilities.")
    states: list[dict] = Field(description="Array of client state information including open files and locks.")


class NFSEntry(BaseModel):
    id: int = Field(description="Placeholder identifier.  Not used as there is only one.")
    servers: Annotated[int | None, Field(ge=1, le=256)] = Field(
        description=(
            "Specify the number of nfsd. Set `1..256`, or `null`/unset to have the server determine the count "
            "automatically. When automatic, the count equals the number of CPU cores, clamped to no less than 1 and "
            "no more than 32. The number of mountd processes is always one quarter of the number of nfsd."
        ),
    )
    allow_nonroot: bool = Field(description="Allow non-root mount requests.  This equates to 'insecure' share option.")
    protocols: list[NFS_protocols] = Field(
        description=(
            "Specify supported NFS protocols:  NFSv3, NFSv4 or both can be listed. At least one must be enabled. The "
            "`showmount` command is available only while NFSv3 is enabled."
        ),
    )
    v4_krb: bool = Field(description="Force Kerberos authentication on NFS shares.")
    v4_domain: str = Field(
        description=(
            "Specify a DNS domain (NFSv4 only). Overrides the DNS domain for NFSv4 (sets the `Domain` setting in "
            "idmapd.conf)."
        ),
    )
    bindip: list[NonEmptyString] = Field(
        default=[],
        description=(
            "Limit the server IP addresses available for NFS. When empty, NFS listens on all active server addresses."
        ),
    )
    mountd_port: NfsTcpPort = Field(description="Specify the mountd port binding.")
    rpcstatd_port: NfsTcpPort = Field(description="Specify the rpc.statd port binding.")
    rpclockd_port: NfsTcpPort = Field(description="Specify the rpc.lockd port binding.")
    mountd_log: bool = Field(description="Enable or disable mountd logging.")
    statd_lockd_log: bool = Field(description="Enable or disable statd and lockd logging.")
    v4_krb_enabled: bool = Field(description="Status of NFSv4 authentication requirement (status only).")
    userd_manage_gids: bool = Field(description="Enable to allow server to manage gids.")
    keytab_has_nfs_spn: bool = Field(description="Report status of NFS Principal Name in keytab (status only).")
    managed_nfsd: bool = Field(
        description=(
            "Report status of 'servers' field. If true, the number of nfsd is managed by the server (status only)."
        ),
    )
    rdma: bool = Field(
        description=(
            "Enable or disable NFS over RDMA.  Available on supported platforms with an installed RDMA-capable NIC. "
            "NFS over RDMA uses port 20049."
        ),
    )


@single_argument_args("nfs_update")
class NFSUpdateArgs(NFSEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    managed_nfsd: Excluded = excluded_field()
    v4_krb_enabled: Excluded = excluded_field()
    keytab_has_nfs_spn: Excluded = excluded_field()


class NFSUpdateResult(BaseModel):
    result: NFSEntry = Field(description="The updated NFS service configuration.")


class NFSBindipChoicesArgs(BaseModel):
    pass


class NFSBindipChoicesResult(BaseModel):
    """Return a dictionary of IP addresses."""

    result: dict[str, str] = Field(description="Available IP addresses that the NFS service can bind to.")


class NFSClientCountArgs(BaseModel):
    pass


class NFSClientCountResult(BaseModel):
    result: int = Field(description="Current number of connected NFS clients.")


class SharingNFSEntry(BaseModel):
    id: int = Field(description="Unique identifier for the NFS share.")
    path: NonEmptyString = Field(description="Local path to be exported.")
    dataset: str | None = Field(
        description="Dataset name component of the path (e.g., 'tank/share'). Null if path cannot be resolved.",
    )
    relative_path: str | None = Field(
        description=(
            "Relative path component within the dataset (e.g., 'subdir/data'). Null if path cannot be resolved."
        ),
    )
    aliases: list[NonEmptyString] = Field(default=[], description="IGNORED for now.")
    comment: str = Field(default="", description="User comment associated with share.")
    networks: list[NonEmptyString] = Field(
        default=[],
        description=(
            "List of authorized networks that are allowed to access the share having format \"network/mask\" CIDR "
            "notation. Each entry must be unique. If empty, all networks are allowed. Excessively long lists should be "
            "avoided."
        ),
    )
    hosts: list[NonEmptyString] = Field(
        default=[],
        description=(
            "List of IP's/hostnames which are allowed to access the share. No quotes or spaces are allowed. Each entry "
            "must be unique. If empty, all IP's/hostnames are allowed. Excessively long lists should be avoided."
        ),
    )
    ro: bool = Field(default=False, description="Export the share as read only.")
    maproot_user: str | None = Field(default=None, description="Map root user client to a specified user.")
    maproot_group: str | None = Field(default=None, description="Map root group client to a specified group.")
    mapall_user: str | None = Field(default=None, description="Map all client users to a specified user.")
    mapall_group: str | None = Field(default=None, description="Map all client groups to a specified group.")
    security: list[Literal["SYS", "KRB5", "KRB5I", "KRB5P"]] = Field(
        default=[],
        description="Specify the security schema.",
    )
    enabled: bool = Field(default=True, description="Enable or disable the share.")
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
    expose_snapshots: bool = Field(
        default=False,
        description=(
            "Enterprise feature to enable access to the ZFS snapshot directory for the export. Export path must be the "
            "root directory of a ZFS dataset."
        ),
    )
    tier: TierInfo | None = Field(
        default=None,
        description=(
            "Storage tier in which the share's underlying dataset is located. This field is read-only; configure the "
            "dataset's tier via `zfs.tier.dataset_set_tier`. NOTE: this is a licensed feature. Will be `null` if "
            "TrueNAS is unlicensed, if tiering is disabled, or if the pool has no SPECIAL vdev."
        ),
    )


class NfsShareCreate(SharingNFSEntry):
    id: Excluded = excluded_field()
    dataset: Excluded = excluded_field()
    relative_path: Excluded = excluded_field()
    locked: Excluded = excluded_field()
    tier: Excluded = excluded_field()


class SharingNFSCreateArgs(BaseModel):
    data: NfsShareCreate = Field(description="NFS share configuration data for the new share.")


class SharingNFSCreateResult(BaseModel):
    result: SharingNFSEntry = Field(description="The created NFS share configuration.")


class NfsShareUpdate(NfsShareCreate, metaclass=ForUpdateMetaclass):
    pass


class SharingNFSUpdateArgs(BaseModel):
    id: int = Field(description="ID of the NFS share to update.")
    data: NfsShareUpdate = Field(description="Updated NFS share configuration data.")


class SharingNFSUpdateResult(BaseModel):
    result: SharingNFSEntry = Field(description="The updated NFS share configuration.")


class SharingNFSDeleteArgs(BaseModel):
    id: int = Field(description="ID of the NFS share to delete.")


class SharingNFSDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the NFS share is successfully deleted.")
