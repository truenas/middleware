from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from middlewared.api import api_method
from middlewared.api.current import (
    QueryOptions,
    RouteIpv4gwReachableArgs,
    RouteIpv4gwReachableResult,
    RouteSystemRoutesItem,
    StaticRouteCreate,
    StaticRouteCreateArgs,
    StaticRouteCreateResult,
    StaticRouteDeleteArgs,
    StaticRouteDeleteResult,
    StaticRouteEntry,
    StaticRouteUpdate,
    StaticRouteUpdateArgs,
    StaticRouteUpdateResult,
)
from middlewared.service import GenericCRUDService, Service, filterable_api_method, private

from .crud import StaticRouteServicePart
from .route import gateway_is_reachable as _gateway_is_reachable
from .route import get_system_routes as _get_system_routes
from .route_sync import sync_impl as route_sync_impl

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("RouteService", "StaticRouteService")


class RouteService(Service):
    class Config:
        namespace_alias = "routes"
        cli_namespace = "network.route"

    @filterable_api_method(item=RouteSystemRoutesItem, roles=["NETWORK_INTERFACE_READ"], check_annotations=True)
    def system_routes(
        self, filters: list[Any], options: QueryOptions
    ) -> list[RouteSystemRoutesItem] | RouteSystemRoutesItem | int:
        """Query IPv4 and IPv6 routes from the kernel's main routing table.

        Returns routes currently installed in the system, including static routes,
        DHCP-learned routes, and directly connected networks. The default route
        (0.0.0.0/0 or ::/0) will have both network and netmask set to all zeros.
        """
        return _get_system_routes(filters, options)

    @api_method(
        RouteIpv4gwReachableArgs, RouteIpv4gwReachableResult, roles=["NETWORK_INTERFACE_READ"], check_annotations=True
    )
    def ipv4gw_reachable(self, ipv4_gateway: str) -> bool:
        """Get the IPv4 gateway and verify if it is reachable by any interface."""
        return _gateway_is_reachable(ipv4_gateway, 4)

    @private
    def gateway_is_reachable(self, gateway: str, ipv: Literal[4, 6] = 4) -> bool:
        return _gateway_is_reachable(gateway, ipv)

    @private
    def sync(self) -> None:
        route_sync_impl(self.context)


class StaticRouteService(GenericCRUDService[StaticRouteEntry]):
    class Config:
        cli_namespace = "network.static_route"
        entry = StaticRouteEntry
        generic = True
        role_prefix = "NETWORK_INTERFACE"

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = StaticRouteServicePart(self.context)

    @api_method(StaticRouteCreateArgs, StaticRouteCreateResult, audit="Static route create", check_annotations=True)
    async def do_create(self, data: StaticRouteCreate) -> StaticRouteEntry:
        """Create a Static Route.

        Address families of ``gateway`` and ``destination`` should match when creating a static route.
        """
        return await self._svc_part.do_create(data)

    @api_method(StaticRouteUpdateArgs, StaticRouteUpdateResult, audit="Static route update", check_annotations=True)
    async def do_update(self, id_: int, data: StaticRouteUpdate) -> StaticRouteEntry:
        """Update Static Route of ``id``."""
        return await self._svc_part.do_update(id_, data)

    @api_method(StaticRouteDeleteArgs, StaticRouteDeleteResult, audit="Static route delete", check_annotations=True)
    async def do_delete(self, id_: int) -> bool:
        """Delete Static Route of ``id``."""
        await self._svc_part.do_delete(id_)
        return True

    @private
    async def sync(self) -> None:
        await self._svc_part.sync()
