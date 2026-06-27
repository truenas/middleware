from __future__ import annotations

from ipaddress import ip_address, ip_interface, ip_network
from typing import TypeVar

from truenas_pynetif.address.netlink import delete_route, netlink_route

from middlewared.api.current import StaticRouteCreate, StaticRouteEntry, StaticRouteUpdate
from middlewared.service import CRUDServicePart
from middlewared.service_exception import ValidationError
import middlewared.sqlalchemy as sa

from .static_routes_sync import sync_impl as staticroute_sync_impl

StaticRouteValidateT = TypeVar("StaticRouteValidateT", bound=StaticRouteEntry)


class StaticRouteModel(sa.Model):
    __tablename__ = "network_staticroute"

    id = sa.Column(sa.Integer(), primary_key=True)
    sr_destination = sa.Column(sa.String(120))
    sr_gateway = sa.Column(sa.String(42))
    sr_description = sa.Column(sa.String(120))


class StaticRouteServicePart(CRUDServicePart[StaticRouteEntry]):
    _datastore = "network.staticroute"
    _datastore_prefix = "sr_"
    _entry = StaticRouteEntry

    async def do_create(self, data: StaticRouteCreate) -> StaticRouteEntry:
        data = await self.validate(data, "staticroute_create")
        entry = await self._create(data.model_dump())
        await self.sync()
        return entry

    async def do_update(self, id_: int, data: StaticRouteUpdate) -> StaticRouteEntry:
        old = await self.get_instance(id_)
        new = old.updated(data)
        if new == old:
            return new

        new = await self.validate(new, "staticroute_update")
        entry = await self._update(id_, new.model_dump())
        await self.sync()
        return entry

    async def do_delete(self, id_: int) -> None:
        st = await self.get_instance(id_)
        await self._delete(id_)
        await self.to_thread(self._delete_kernel_route, st)

    def _delete_kernel_route(self, st: StaticRouteEntry) -> None:
        try:
            network = ip_network(st.destination, strict=False)
            with netlink_route() as sock:
                delete_route(
                    sock,
                    dst=network.network_address.exploded,
                    dst_len=network.prefixlen,
                    gateway=st.gateway,
                )
        except Exception:
            self.logger.exception("Failed to delete static route %r", st.destination)

    async def sync(self) -> None:
        await self.to_thread(staticroute_sync_impl, self)

    async def validate(self, data: StaticRouteValidateT, schema: str) -> StaticRouteValidateT:
        try:
            # Validate destination: CIDR notation
            dst = ip_interface(data.destination)
        except ValueError as ve:
            raise ValidationError(f"{schema}.destination", str(ve))

        try:
            # Validate gateway: IP address (not CIDR)
            gw = ip_address(data.gateway)
        except ValueError as ve:
            raise ValidationError(f"{schema}.gateway", str(ve))

        if dst.version != gw.version:
            raise ValidationError(
                f"{schema}.destination",
                "Destination and gateway address families must match",
            )

        return data.model_copy(update={"destination": dst.exploded, "gateway": gw.exploded})
