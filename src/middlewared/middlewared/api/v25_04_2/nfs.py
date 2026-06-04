from typing import Annotated, Literal, TypeAlias

from pydantic import (
    Field, AfterValidator
)

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString,
    single_argument_args,
    TcpPort, exclude_tcp_ports
)

__all__ = ["NFSEntry",
           "NFSUpdateArgs", "NFSUpdateResult",
           "NFSBindipChoicesArgs", "NFSBindipChoicesResult",
           "SharingNFSEntry",
           "SharingNFSCreateArgs", "SharingNFSCreateResult",
           "SharingNFSUpdateArgs", "SharingNFSUpdateResult",
           "SharingNFSDeleteArgs", "SharingNFSDeleteResult"]

MAX_NUM_NFS_NETWORKS = 42
MAX_NUM_NFS_HOSTS = 42
NFS_protocols = Literal["NFSV3", "NFSV4"]
NFS_RDMA_DEFAULT_PORT = 20049
EXCLUDED_PORTS = [NFS_RDMA_DEFAULT_PORT]
NfsTcpPort: TypeAlias = Annotated[TcpPort | None, AfterValidator(exclude_tcp_ports(EXCLUDED_PORTS))]


class NFSEntry(BaseModel):
    id: int
    servers: Annotated[int | None, Field(ge=1, le=256)] = Field(
        description="Specify the number of nfsd. Default: Number of nfsd is equal number of CPU.",
    )
    allow_nonroot: bool = Field(description="Allow non-root mount requests.  This equates to 'insecure' share option.")
    protocols: list[NFS_protocols] = Field(
        description="Specify supported NFS protocols:  NFSv3, NFSv4 or both can be listed.",
    )
    v4_krb: bool = Field(description="Force Kerberos authentication on NFS shares.")
    v4_domain: str = Field(description="Specify a DNS domain (NFSv4 only).")
    bindip: list[NonEmptyString] = Field(default=[], description="Limit the server IP addresses available for NFS.")
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
            "Report status of 'servers' field. If True the number of nfsd are managed by the server (status only)."
        ),
    )
    rdma: bool = Field(description="Enable or disable NFS over RDMA.  Requires RDMA capable NIC.")


@single_argument_args('nfs_update')
class NFSUpdateArgs(NFSEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    managed_nfsd: Excluded = excluded_field()
    v4_krb_enabled: Excluded = excluded_field()
    keytab_has_nfs_spn: Excluded = excluded_field()


class NFSUpdateResult(BaseModel):
    result: NFSEntry


class NFSBindipChoicesArgs(BaseModel):
    pass


class NFSBindipChoicesResult(BaseModel):
    """ Return a dictionary of IP addresses """
    result: dict[str, str]


class SharingNFSEntry(BaseModel):
    id: int
    path: NonEmptyString = Field(description="Local path to be exported.")
    aliases: list[NonEmptyString] = Field(default=[], description="IGNORED for now.")
    comment: str = Field(default="", description="User comment associated with share.")
    networks: Annotated[list[NonEmptyString], Field(max_length=MAX_NUM_NFS_NETWORKS)] = Field(
        default=[],
        description=(
            "List of authorized networks that are allowed to access the share having format \"network/mask\" CIDR "
            "notation. Each entry must be unique. If empty, all networks are allowed. Maximum number of entries: 42"
        ),
    )
    hosts: Annotated[list[NonEmptyString], Field(max_length=MAX_NUM_NFS_HOSTS)] = Field(
        default=[],
        description=(
            "list of IP's/hostnames which are allowed to access the share.  No quotes or spaces are allowed. Each entry"
            " must be unique. If empty, all IP's/hostnames are allowed. Maximum number of entries: 42"
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
    locked: bool | None = Field(description="Lock state of the dataset (if encrypted).")
    expose_snapshots: bool = Field(
        default=False,
        description=(
            "Enterprise feature to enable access to the ZFS snapshot directory for the export. Export path must be the "
            "root directory of a ZFS dataset."
        ),
    )


class NfsShareCreate(SharingNFSEntry):
    id: Excluded = excluded_field()
    locked: Excluded = excluded_field()


class SharingNFSCreateArgs(BaseModel):
    data: NfsShareCreate


class SharingNFSCreateResult(BaseModel):
    result: SharingNFSEntry


class NfsShareUpdate(NfsShareCreate, metaclass=ForUpdateMetaclass):
    pass


class SharingNFSUpdateArgs(BaseModel):
    id: int
    data: NfsShareUpdate


class SharingNFSUpdateResult(BaseModel):
    result: SharingNFSEntry


class SharingNFSDeleteArgs(BaseModel):
    id: int


class SharingNFSDeleteResult(BaseModel):
    result: Literal[True]
