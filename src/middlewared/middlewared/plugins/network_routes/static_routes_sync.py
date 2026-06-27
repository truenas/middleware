from ipaddress import ip_network

from truenas_pynetif.address.constants import AddressFamily
from truenas_pynetif.address.netlink import (
    add_route,
    delete_route,
    get_default_route,
    get_routes,
    netlink_route,
)

from middlewared.api.current import StaticRouteEntry
from middlewared.service import ServiceContext

__all__ = ("sync_impl",)


def _parse_static_route(staticroute: StaticRouteEntry) -> tuple[str, int, str]:
    """Parse a static route DB record into (dst, dst_len, gateway)."""
    network = ip_network(staticroute.destination, strict=False)
    return network.network_address.exploded, network.prefixlen, staticroute.gateway


def sync_impl(ctx: ServiceContext) -> None:
    """Synchronize kernel static routes with the database configuration."""
    desired: dict[tuple[str | None, int, str | None], bool] = {}
    for static_route in ctx.call_sync2(ctx.s.staticroute.query):
        key = _parse_static_route(static_route)
        desired[key] = True

    with netlink_route() as sock:
        default_ipv4 = get_default_route(sock, family=AddressFamily.INET)
        default_ipv6 = get_default_route(sock, family=AddressFamily.INET6)

        default_keys = set()
        if default_ipv4:
            default_keys.add(
                (default_ipv4.dst, default_ipv4.dst_len, default_ipv4.gateway)
            )
        if default_ipv6:
            default_keys.add(
                (default_ipv6.dst, default_ipv6.dst_len, default_ipv6.gateway)
            )

        for route in get_routes(sock):
            route_key = (route.dst, route.dst_len, route.gateway)
            if route_key in desired:
                del desired[route_key]
                continue

            if route_key in default_keys:
                continue

            if route.gateway is not None:
                ctx.logger.debug(
                    "Removing route %s/%s via %s",
                    route.dst,
                    route.dst_len,
                    route.gateway,
                )
                try:
                    delete_route(
                        sock,
                        dst=route.dst,
                        dst_len=route.dst_len,
                        gateway=route.gateway,
                        index=route.oif,
                        table=route.table,
                        scope=route.scope,
                    )
                except Exception:
                    ctx.logger.exception("Failed to remove route")

        for dst, dst_len, gateway in desired:
            ctx.logger.debug("Adding route %s/%s via %s", dst, dst_len, gateway)
            try:
                add_route(sock, dst=dst, dst_len=dst_len, gateway=gateway)
            except Exception:
                ctx.logger.exception("Failed to add route")
