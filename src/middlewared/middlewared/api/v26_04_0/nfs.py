from typing import Annotated, Literal, TypeAlias

from pydantic import Field, AfterValidator

from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    NonEmptyString,
    single_argument_args,
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

NFS_protocols = Literal["NFSV3", "NFSV4"]
NFS_RDMA_DEFAULT_PORT = 20049
EXCLUDED_PORTS = [NFS_RDMA_DEFAULT_PORT]
NfsTcpPort: TypeAlias = Annotated[
    TcpPort | None, AfterValidator(exclude_tcp_ports(EXCLUDED_PORTS))
]


class NFSGetNfs3ClientsEntry(BaseModel):
    ip: str
    """IP address of the NFSv3 client."""
    export: str
    """NFS export path being accessed by the client."""


class NFSGetNfs4ClientsEntry(BaseModel):
    id: str
    """Unique identifier for the NFSv4 client."""
    info: dict
    """Client information including connection details and capabilities."""
    states: list[dict]
    """Array of client state information including open files and locks."""


class NfsEntry(BaseModel):
    id: int
    """Placeholder identifier.  Not used as there is only one."""
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
    If true, the number of nfsd is managed by the server (status only). """
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
    """The updated NFS service configuration."""


class NFSBindipChoicesArgs(BaseModel):
    pass


class NFSBindipChoicesResult(BaseModel):
    """Return a dictionary of IP addresses."""

    result: dict[str, str]
    """Available IP addresses that the NFS service can bind to."""


class NFSClientCountArgs(BaseModel):
    pass


class NFSClientCountResult(BaseModel):
    result: int
    """Current number of connected NFS clients."""


class NfsShareEntry(BaseModel):
    id: int
    """Unique identifier for the NFS share."""
    path: NonEmptyString
    """ Local path to be exported. """
    aliases: list[NonEmptyString] = []
    """ IGNORED for now. """
    comment: str = ""
    """ User comment associated with share. """
    networks: list[NonEmptyString] = []
    """
    List of authorized networks that are allowed to access the share having format
    "network/mask" CIDR notation. Each entry must be unique. If empty, all networks are allowed.
    Excessively long lists should be avoided.
    """
    hosts: list[NonEmptyString] = []
    """
    List of IP's/hostnames which are allowed to access the share.  No quotes or spaces are allowed.
    Each entry must be unique. If empty, all IP's/hostnames are allowed.
    Excessively long lists should be avoided.
    """
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
    """ Read-only value indicating whether the share is located on a locked dataset.

    Returns:
        - True: The share is in a locked dataset.
        - False: The share is not in a locked dataset.
        - None: Lock status is not available because path locking information was not requested.
    """
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
    """NFS share configuration data for the new share."""


class SharingNFSCreateResult(BaseModel):
    result: NfsShareEntry
    """The created NFS share configuration."""


class NfsShareUpdate(NfsShareCreate, metaclass=ForUpdateMetaclass):
    pass


class SharingNFSUpdateArgs(BaseModel):
    id: int
    """ID of the NFS share to update."""
    data: NfsShareUpdate
    """Updated NFS share configuration data."""


class SharingNFSUpdateResult(BaseModel):
    result: NfsShareEntry
    """The updated NFS share configuration."""


class SharingNFSDeleteArgs(BaseModel):
    id: int
    """ID of the NFS share to delete."""


class SharingNFSDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the NFS share is successfully deleted."""
