from typing import Annotated, Literal, TypeAlias

from pydantic import Field, AfterValidator

from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    NonEmptyString,
    single_argument_args,
    single_argument_result,
    TcpPort,
    exclude_tcp_ports,
)

__all__ = [
    "NFSGetNfs3ClientsEntry",
    "NFSGetNfs4ClientsEntry",
    "NfsEntry",
    "NFSBindipChoicesArgs",
    "NFSBindipChoicesResult",
    "NFSClientCountArgs",
    "NFSClientCountResult",
    "NfsShareEntry",
    "SharingNFSCreateArgs",
    "SharingNFSCreateResult",
    "SharingNFSUpdateArgs",
    "SharingNFSUpdateResult",
    "SharingNFSDeleteArgs",
    "SharingNFSDeleteResult",
    "NFSUpdateArgs",
    "NFSUpdateResult",
]

MAX_NUM_NFS_NETWORKS = 42
MAX_NUM_NFS_HOSTS = 42
NFS_protocols = Literal["NFSV3", "NFSV4"]
NFS_RDMA_DEFAULT_PORT = 20049
EXCLUDED_PORTS = [NFS_RDMA_DEFAULT_PORT]
NfsTcpPort: TypeAlias = Annotated[
    TcpPort | None, AfterValidator(exclude_tcp_ports(EXCLUDED_PORTS))
]


class NFSGetNfs3ClientsEntry(BaseModel):
    ip: str
    export: str


class NFSGetNfs4ClientsEntry(BaseModel):
    id: str
    info: dict
    states: list[dict]


class NfsEntry(BaseModel):
    id: int
    servers: Annotated[int | None, Field(ge=1, le=256)]
    """ Specify the number of nfsd. Default: Number of nfsd is equal number of CPU. """
    allow_nonroot: bool
    """ Allow non-root mount requests.  This equates to 'insecure' share option. """
    protocols: list[NFS_protocols]
    """ Specify supported NFS protocols:  NFSv3, NFSv4 or both can be listed. """
    v4_krb: bool
    """ Force Kerberos authentication on NFS shares. """
    v4_domain: str
    """ Specify a DNS domain (NFSv4 only). """
    bindip: list[NonEmptyString] = []
    """ Limit the server IP addresses available for NFS. """
    mountd_port: NfsTcpPort
    """ Specify the mountd port binding. """
    rpcstatd_port: NfsTcpPort
    """ Specify the rpc.statd port binding. """
    rpclockd_port: NfsTcpPort
    """ Specify the rpc.lockd port binding. """
    mountd_log: bool
    """ Enable or disable mountd logging. """
    statd_lockd_log: bool
    """ Enable or disable statd and lockd logging. """
    v4_krb_enabled: bool
    """ Status of NFSv4 authentication requirement (status only). """
    userd_manage_gids: bool
    """ Enable to allow server to manage gids. """
    keytab_has_nfs_spn: bool
    """ Report status of NFS Principal Name in keytab (status only). """
    managed_nfsd: bool
    """ Report status of 'servers' field.
    If True the number of nfsd are managed by the server (status only). """
    rdma: bool
    """ Enable or disable NFS over RDMA.  Requires RDMA capable NIC. """


@single_argument_args("nfs_update")
class NFSUpdateArgs(NfsEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    managed_nfsd: Excluded = excluded_field()
    v4_krb_enabled: Excluded = excluded_field()
    keytab_has_nfs_spn: Excluded = excluded_field()


class NFSUpdateResult(BaseModel):
    result: NfsEntry


class NFSBindipChoicesArgs(BaseModel):
    pass


class NFSBindipChoicesResult(BaseModel):
    """Return a dictionary of IP addresses"""

    result: dict[str, str]


class NFSClientCountArgs(BaseModel):
    pass


class NFSClientCountResult(BaseModel):
    result: int


class NfsShareEntry(BaseModel):
    id: int
    path: NonEmptyString
    """ Local path to be exported. """
    aliases: list[NonEmptyString] = []
    """ IGNORED for now. """
    comment: str = ""
    """ User comment associated with share. """
    networks: Annotated[
        list[NonEmptyString], Field(max_length=MAX_NUM_NFS_NETWORKS)
    ] = []
    """ List of authorized networks that are allowed to access the share having format
        "network/mask" CIDR notation. Each entry must be unique. If empty, all networks are allowed.
        Maximum number of entries: 42 """
    hosts: Annotated[list[NonEmptyString], Field(max_length=MAX_NUM_NFS_HOSTS)] = []
    """ list of IP's/hostnames which are allowed to access the share.  No quotes or spaces are allowed.
        Each entry must be unique. If empty, all IP's/hostnames are allowed.
        Maximum number of entries: 42 """
    ro: bool = False
    """ Export the share as read only. """
    maproot_user: str | None = None
    """ Map root user client to a specified user. """
    maproot_group: str | None = None
    """ Map root group client to a specified group. """
    mapall_user: str | None = None
    """ Map all client users to a specified user. """
    mapall_group: str | None = None
    """ Map all client groups to a specified group. """
    security: list[Literal["SYS", "KRB5", "KRB5I", "KRB5P"]] = []
    """ Specify the security schema. """
    enabled: bool = True
    """ Enable or disable the share. """
    locked: bool | None
    """ Lock state of the dataset (if encrypted). """
    expose_snapshots: bool = False
    """
    Enterprise feature to enable access to the ZFS snapshot directory for the export.
    Export path must be the root directory of a ZFS dataset.
    """


class NfsShareCreate(NfsShareEntry):
    id: Excluded = excluded_field()
    locked: Excluded = excluded_field()


class SharingNFSCreateArgs(BaseModel):
    data: NfsShareCreate


class SharingNFSCreateResult(BaseModel):
    result: NfsShareEntry


class NfsShareUpdate(NfsShareCreate, metaclass=ForUpdateMetaclass):
    pass


class SharingNFSUpdateArgs(BaseModel):
    id: int
    data: NfsShareUpdate


class SharingNFSUpdateResult(BaseModel):
    result: NfsShareEntry


class SharingNFSDeleteArgs(BaseModel):
    id: int


class SharingNFSDeleteResult(BaseModel):
    result: Literal[True]
