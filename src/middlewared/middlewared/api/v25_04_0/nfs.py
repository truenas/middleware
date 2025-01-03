from typing import Annotated, Literal

from pydantic import AfterValidator, Field, IPvAnyAddress

from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    single_argument_args,
    TcpPort
)

__all__ = ["NfsEntry",
           "NfsUpdateArgs", "NfsUpdateResult"]

NFS_protocols = Literal["NFSv3", "NFSv4"]
NFS_RDMA_DEFAULT_PORT = 20049
EXCLUDED_PORTS = [NFS_RDMA_DEFAULT_PORT]


def exclude_ports(value: int) -> int:
    if value in EXCLUDED_PORTS:
        raise ValueError(
            f'{value} is a reserved for internal use. Please select another value.'
        )
    return value


class NfsEntry(BaseModel):
    id: int
    servers: Annotated[int, Field(ge=1, le=256)] | None = None
    """ Specify the number of nfsd. Default: Number of nfsd is equal number of CPU. """
    allow_nonroot: bool
    """ Allow non-root mount requests.  This equates to 'insecure' share option. """
    protocols: list[NFS_protocols] = ["NFSv3", "NFSv4"]
    """ Specify supported NFS protocols:  NFSv3, NFSv4 or both can be listed. """
    v4_krb: bool
    """ Force Kerberos authentication on NFS shares. """
    v4_domain: str
    """ Specify a DNS domain (NFSv4 only) """
    bindip: list[IPvAnyAddress] = []
    """ Limit the server IP addresses available for NFS """
    mountd_port: Annotated[TcpPort, AfterValidator(exclude_ports)] | None
    """ Specify the mountd port binding """
    rpcstatd_port: Annotated[TcpPort, AfterValidator(exclude_ports)] | None
    """ Specify the rpc.statd port binding """
    rpclock_port: Annotated[TcpPort, AfterValidator(exclude_ports)] | None
    """ Specify the rpc.lockd port binding """
    mountd_log: bool
    """ Enable or disable mountd logging """
    statd_lockd_log: bool
    """ Enable or disable statd and lockd logging """
    v4_krb_enabled: bool
    """ Status of NFSv4 authentication requirement (status only) """
    userd_manage_gids: bool
    """ Enable to allow server to manage gids """
    keytab_has_nfs_spn: bool
    """ Report status of NFS Principal Name in keytab (status only)"""
    managed_nfsd: bool
    """ Report status of 'servers' field.
    If True the number of nfsd are managed by the server. (status only)"""
    rdma: bool = False
    """ Enable or disable NFS over RDMA.  Requires RDMA capable NIC """


@single_argument_args('nfs_update')
class NfsUpdateArgs(NfsEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    managed_nfsd: Excluded = excluded_field()
    v4_krb_enabled: Excluded = excluded_field()
    keytab_has_nfs_spn: Excluded = excluded_field()


class NfsUpdateResult(BaseModel):
    result: NfsEntry
