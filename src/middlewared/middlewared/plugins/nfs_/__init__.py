from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api import api_method
from middlewared.api.current import (
    NFSBindipChoicesArgs,
    NFSBindipChoicesResult,
    NFSClientCountArgs,
    NFSClientCountResult,
    NFSEntry,
    NFSGetNfs3ClientsEntry,
    NFSGetNfs4ClientsEntry,
    NFSUpdate,
    NFSUpdateArgs,
    NFSUpdateResult,
    QueryOptions,
)
from middlewared.common.listen import SystemServiceListenMultipleDelegate
from middlewared.service import SystemServiceService, filterable_api_method
from middlewared.utils.filter_list import filter_list

from . import debug, directories, status
from .config import NFSServicePart, bindip_choices
from .debug import NfsDebug, NFSGetDebugArgs, NFSGetDebugResult, NFSSetDebugArgs, NFSSetDebugResult
from .directories import (
    BuiltinName,
    NFSNameToIdConversionArgs,
    NFSNameToIdConversionResult,
    NFSSetupDirectoriesArgs,
    NFSSetupDirectoriesResult,
)
from .sec import NFSSecArgs, NFSSecResult, NfsSecurityFlavor, security_flavors
from .status import (
    NFSClearNfs3RmtabArgs,
    NFSClearNfs3RmtabResult,
    NFSCloseClientStateArgs,
    NFSCloseClientStateResult,
    NFSGetNfs4ClientInfoArgs,
    NFSGetNfs4ClientInfoResult,
    NFSGetNfs4ClientStatesArgs,
    NFSGetNfs4ClientStatesResult,
    NFSGetRmtabArgs,
    NFSGetRmtabResult,
    NFSGetThreadpoolModeArgs,
    NFSGetThreadpoolModeResult,
    NFSSetThreadpoolModeArgs,
    NFSSetThreadpoolModeResult,
    ThreadpoolMode,
)

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("NFSService",)


class NFSService(SystemServiceService[NFSEntry]):
    class Config:
        cli_namespace = "service.nfs"
        entry = NFSEntry
        generic = True
        role_prefix = "SHARING_NFS"
        service = "nfs"
        service_verb = "restart"

    def __init__(self, middleware: Middleware):
        super().__init__(middleware)
        self._service_part = NFSServicePart(self.context)

    async def config(self) -> NFSEntry:
        return await self._service_part.config()

    @api_method(NFSBindipChoicesArgs, NFSBindipChoicesResult, check_annotations=True)
    async def bindip_choices(self) -> dict[str, str]:
        """
        Returns ip choices for NFS service to use.
        """
        return await bindip_choices(self.context)

    @api_method(NFSUpdateArgs, NFSUpdateResult, audit="Update NFS configuration", check_annotations=True)
    async def do_update(self, data: NFSUpdate) -> NFSEntry:
        """
        Update the NFS service configuration.

        At least one protocol must remain enabled in ``protocols``; the ``showmount`` command is available only
        while NFSv3 is enabled. When ``servers`` is ``null``, the number of nfsd is determined automatically from
        the system's capabilities (between 1 and 32); otherwise it is set to the requested value (1 to 256). The
        number of mountd processes is always one quarter of the number of nfsd. When ``bindip`` is empty, NFS
        listens on all active server addresses. NFS over RDMA, enabled with ``rdma``, is only available on
        supported platforms with an RDMA-capable NIC and uses port 20049.
        """
        return await self._service_part.do_update(data)

    @api_method(NFSSecArgs, NFSSecResult, private=True, check_annotations=True)
    def sec(self, config: NFSEntry, has_nfs_principal: bool) -> list[NfsSecurityFlavor]:
        return security_flavors(config, has_nfs_principal)

    @api_method(NFSNameToIdConversionArgs, NFSNameToIdConversionResult, private=True, check_annotations=True)
    def name_to_id_conversion(self, name: BuiltinName, name_type: str = "user") -> BuiltinName:
        return directories.name_to_id_conversion(self.context, name, name_type)

    @api_method(NFSSetupDirectoriesArgs, NFSSetupDirectoriesResult, private=True, check_annotations=True)
    def setup_directories(self) -> None:
        directories.setup_directories(self.context)

    @api_method(NFSGetDebugArgs, NFSGetDebugResult, private=True, check_annotations=True)
    def get_debug(self) -> NfsDebug:
        return debug.get_debug()

    @api_method(NFSSetDebugArgs, NFSSetDebugResult, private=True, check_annotations=True)
    def set_debug(self, svcs: NfsDebug) -> bool:
        return debug.set_debug(svcs)

    @api_method(NFSGetRmtabArgs, NFSGetRmtabResult, private=True, check_annotations=True)
    def get_rmtab(self) -> list[NFSGetNfs3ClientsEntry]:
        return status.get_rmtab()

    @api_method(NFSClearNfs3RmtabArgs, NFSClearNfs3RmtabResult, private=True, check_annotations=True)
    def clear_nfs3_rmtab(self, ip_to_clear: list[str] | None = None) -> None:
        status.clear_nfs3_rmtab(ip_to_clear)

    @filterable_api_method(
        item=NFSGetNfs3ClientsEntry,
        # NFS_WRITE because this exposes hostnames and IP addresses
        # READONLY is considered administrative-level permission
        roles=["READONLY_ADMIN", "SHARING_NFS_WRITE"],
        check_annotations=True,
    )
    def get_nfs3_clients(
        self,
        filters: list[Any],
        options: QueryOptions,
    ) -> list[NFSGetNfs3ClientsEntry] | NFSGetNfs3ClientsEntry | int:
        """
        Read contents of rmtab. This information may not
        be accurate due to stale entries. This is ultimately
        a limitation of the NFSv3 protocol.
        """
        return filter_list(status.get_rmtab(), filters, options, NFSGetNfs3ClientsEntry)

    @api_method(NFSGetNfs4ClientInfoArgs, NFSGetNfs4ClientInfoResult, private=True, check_annotations=True)
    def get_nfs4_client_info(self, id_: str) -> dict[str, Any]:
        return status.get_nfs4_client_info(id_)

    @api_method(NFSGetNfs4ClientStatesArgs, NFSGetNfs4ClientStatesResult, private=True, check_annotations=True)
    def get_nfs4_client_states(self, id_: str) -> list[Any]:
        return status.get_nfs4_client_states(id_)

    @filterable_api_method(
        item=NFSGetNfs4ClientsEntry,
        # NFS_WRITE because this exposes hostnames, IP addresses and other details
        # READONLY is considered administrative-level permission
        roles=["READONLY_ADMIN", "SHARING_NFS_WRITE"],
        check_annotations=True,
    )
    def get_nfs4_clients(
        self,
        filters: list[Any],
        options: QueryOptions,
    ) -> list[NFSGetNfs4ClientsEntry] | NFSGetNfs4ClientsEntry | int:
        """
        Read information about NFSv4 clients from /proc/fs/nfsd/clients.

        Sample output::

            [{
                "id": "4",
                "info": {
                    "clientid": 6273260596088110000,
                    "address": "192.168.40.247:790",
                    "status": "confirmed",
                    "seconds from last renew": 45,
                    "name": "Linux NFSv4.2 debian12-hv",
                    "minor version": 2,
                    "Implementation domain": "kernel.org",
                    "Implementation name": "Linux 6.1.0-12-amd64 #1 SMP PREEMPT_DYNAMIC Debian 6.1.52-1 x86_64",
                    "Implementation time": [0, 0],
                    "callback state": "UP",
                    "callback address": "192.168.40.247:0"
                },
                "states": [
                    {
                        "94850248556250062041657638912": {
                            "type": "deleg",
                            "access": "r",
                            "superblock": "00:39:5",
                            "filename": "/debian12-hv"
                        }
                    },
                    {
                        "94850248556250062041741524992": {
                            "type": "open",
                            "access": "rw",
                            "deny": "--",
                            "superblock": "00:39:137",
                            "filename": "/.debian12-hv.swp",
                            "owner": "open id:\u0000\u0000\u00008\u0000\u0000\u0000\u0000\u0000\u0000\u0014þÀ²3"
                        }
                    }
                ]
            }]

        Description of the fields (all per NFS client)::

            'clientid': Hash generated for this client connection
            'address':  The client IP and port. e.g. 10.20.30.40:768

            'status':   The current client status:
                'confirmed' An active connection.
                            The status will convert to 'courtesy' in 90 seconds if not 'confirmed' by the client.
                'courtesy'  A stalled connection from an inactive client.
                            The status will convert to 'expirable' in 24hr.
                'expirable' Waiting to be cleaned up.

            'seconds from last renew':  The session timeout counter.  See 'status' field.
                                        Gets reset by confirmation update from the client

            'name': Supplied by the client.
                    Linux clients might offer something like 'Linux NFS4.2 clnt_name'.
                    FreeBSD clients might supply a UUID like name

            'minor version':    The NFS4.x minor version.  E.G. '2' for NFSv4.2

            'Implementation domain': NFSv4.1 info - e.g. 'kernel.org' or 'freebsd.org'.
            'Implementation name':   NFSv4.1 info - e.g. equivalent to 'uname -a' on the client
            'Implementation time':   NFSv4.1 info - Timestamp (time nfstime4) of client version (maybe unused?)

            'callback state':   Current callback 'service' status for this client: 'UP', 'DOWN', 'FAULT' or 'UNKNOWN'
                                Linux clients usually indicate 'UP'
                                FreeBSD clients may indicate 'DOWN' but are still functional
        """
        return filter_list(status.get_nfs4_clients(), filters, options, NFSGetNfs4ClientsEntry)

    @api_method(NFSClientCountArgs, NFSClientCountResult, roles=["SHARING_NFS_READ"], check_annotations=True)
    def client_count(self) -> int:
        """
        Return currently connected clients count.
        Count may not be accurate if NFSv3 protocol is in use
        due to potentially stale rmtab entries.
        """
        return len(status.get_rmtab()) + len(status.get_nfs4_clients())

    @api_method(NFSCloseClientStateArgs, NFSCloseClientStateResult, private=True, check_annotations=True)
    def close_client_state(self, client_id: str) -> None:
        status.close_client_state(client_id)

    @api_method(NFSGetThreadpoolModeArgs, NFSGetThreadpoolModeResult, private=True, check_annotations=True)
    def get_threadpool_mode(self) -> ThreadpoolMode:
        return status.get_threadpool_mode()

    @api_method(NFSSetThreadpoolModeArgs, NFSSetThreadpoolModeResult, private=True, check_annotations=True)
    def set_threadpool_mode(self, pool_mode: ThreadpoolMode) -> None:
        status.set_threadpool_mode(pool_mode)


async def setup(middleware: Middleware) -> None:
    await middleware.call(
        "interface.register_listen_delegate",
        SystemServiceListenMultipleDelegate(middleware, "nfs", "bindip"),
    )
