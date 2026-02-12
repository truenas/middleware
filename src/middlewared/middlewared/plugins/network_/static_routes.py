from ipaddress import ip_address, ip_interface, ip_network

from middlewared.api import api_method
from middlewared.api.current import (
    StaticRouteEntry,
    StaticRouteUpdateArgs,
    StaticRouteUpdateResult,
    StaticRouteCreateArgs,
    StaticRouteCreateResult,
    StaticRouteDeleteArgs,
    StaticRouteDeleteResult,
)
import middlewared.sqlalchemy as sa
from middlewared.plugins.network_.static_routes_sync import (
    sync_impl as staticroute_sync_impl,
)
from middlewared.service import CRUDService, private
from middlewared.service_exception import ValidationError
from truenas_pynetif.address.netlink import delete_route, netlink_route


class StaticRouteModel(sa.Model):
    __tablename__ = "network_staticroute"

    id = sa.Column(sa.Integer(), primary_key=True)
    sr_destination = sa.Column(sa.String(120))
    sr_gateway = sa.Column(sa.String(42))
    sr_description = sa.Column(sa.String(120))


class StaticRouteService(CRUDService):
    class Config:
        datastore = "network.staticroute"
        datastore_prefix = "sr_"
        cli_namespace = "network.static_route"
        entry = StaticRouteEntry
        role_prefix = "NETWORK_INTERFACE"

    @api_method(
        StaticRouteCreateArgs,
        StaticRouteCreateResult,
        audit="Static route create"
    )
    def do_create(self, data):
        """
        Create a Static Route.

        Address families of `gateway` and `destination` should match when creating a static route.

        `description` is an optional attribute for any notes regarding the static route.
        """
        self._validate("staticroute_create", data)
        id_ = self.middleware.call_sync(
            "datastore.insert",
            self._config.datastore,
            data,
            {"prefix": self._config.datastore_prefix},
        )
        self.sync()
        return self.get_instance__sync(id_)

    @api_method(
        StaticRouteUpdateArgs,
        StaticRouteUpdateResult,
        audit="Static route update"
    )
    def do_update(self, id_, data):
        """
        Update Static Route of `id`.
        """
        old = self.get_instance__sync(id_)
        new = old.copy()
        new.update(data)
        if new == old:
            return new

        self._validate("staticroute_update", new)
        self.middleware.call_sync(
            "datastore.update",
            self._config.datastore,
            id_,
            new,
            {"prefix": self._config.datastore_prefix},
        )
        self.sync()
        return self.get_instance__sync(id_)

    @api_method(
        StaticRouteDeleteArgs,
        StaticRouteDeleteResult,
        audit="Static route delete"
    )
    def do_delete(self, id_):
        """
        Delete Static Route of `id`.
        """
        st = self.get_instance__sync(id_)
        rv = self.middleware.call_sync("datastore.delete", self._config.datastore, id_)
        try:
            network = ip_network(st["destination"], strict=False)
            with netlink_route() as sock:
                delete_route(
                    sock,
                    dst=network.network_address.exploded,
                    dst_len=network.prefixlen,
                    gateway=st["gateway"],
                )
        except Exception:
            self.logger.exception("Failed to delete static route %r", st["destination"])

        return rv

    @private
    def sync(self):
        """Synchronize kernel static routes with the database configuration."""
        staticroute_sync_impl(self)

    @private
    def _validate(self, schema_name: str, data: dict) -> None:
        dst, gw = data.pop("destination"), data.pop("gateway")
        try:
            # Validate destination: CIDR notation
            dst = ip_interface(dst)
        except ValueError as ve:
            raise ValidationError(f"{schema_name}.destination", str(ve))

        try:
            # Validate gateway: IP address (not CIDR)
            gw = ip_address(gw)
        except ValueError as ve:
            raise ValidationError(f"{schema_name}.gateway", str(ve))

        if dst.version != gw.version:
            raise ValidationError(
                f"{schema_name}.destination",
                "Destination and gateway address families must match",
            )
        else:
            data["destination"] = dst.exploded
            data["gateway"] = gw.exploded
