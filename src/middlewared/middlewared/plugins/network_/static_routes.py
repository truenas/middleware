from ipaddress import ip_interface, ip_address

from truenas_pynetif.routing import Route, RoutingTable

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
from middlewared.service import CRUDService, private
from middlewared.service_exception import ValidationErrors


class StaticRouteModel(sa.Model):
    __tablename__ = 'network_staticroute'

    id = sa.Column(sa.Integer(), primary_key=True)
    sr_destination = sa.Column(sa.String(120))
    sr_gateway = sa.Column(sa.String(42))
    sr_description = sa.Column(sa.String(120))


class StaticRouteService(CRUDService):
    class Config:
        datastore = 'network.staticroute'
        datastore_prefix = 'sr_'
        cli_namespace = 'network.static_route'
        entry = StaticRouteEntry
        role_prefix = 'NETWORK_INTERFACE'

    @api_method(
        StaticRouteCreateArgs,
        StaticRouteCreateResult,
        audit='Static route create'
    )
    async def do_create(self, data):
        """
        Create a Static Route.

        Address families of `gateway` and `destination` should match when creating a static route.

        `description` is an optional attribute for any notes regarding the static route.
        """
        verrors = ValidationErrors()
        self._validate('staticroute_create', verrors, data)
        verrors.check()

        id_ = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await (await self.middleware.call('service.control', 'RESTART', 'routing')).wait(raise_error=True)

        return await self.get_instance(id_)

    @api_method(
        StaticRouteUpdateArgs,
        StaticRouteUpdateResult,
        audit='Static route update'
    )
    async def do_update(self, id_, data):
        """
        Update Static Route of `id`.
        """
        old = await self.get_instance(id_)
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        self._validate('staticroute_update', verrors, new)
        verrors.check()

        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix})

        await (await self.middleware.call('service.control', 'RESTART', 'routing')).wait(raise_error=True)

        return await self.get_instance(id_)

    @api_method(
        StaticRouteDeleteArgs,
        StaticRouteDeleteResult,
        audit='Static route delete'
    )
    def do_delete(self, id_):
        """
        Delete Static Route of `id`.
        """
        st = self.middleware.call_sync('staticroute.get_instance', id_)
        rv = self.middleware.call_sync('datastore.delete', self._config.datastore, id_)
        try:
            rt = RoutingTable()
            rt.delete(self._netif_route(st))
        except Exception:
            self.logger.exception('Failed to delete static route %r', st['destination'])

        return rv

    @private
    def sync(self):
        new_routes = list()
        for route in self.middleware.call_sync('staticroute.query'):
            new_routes.append(self._netif_route(route))

        rt = RoutingTable()
        default_route_ipv4 = rt.default_route_ipv4
        default_route_ipv6 = rt.default_route_ipv6
        for route in rt.routes:
            if route in new_routes:
                new_routes.remove(route)
                continue

            if route not in [default_route_ipv4, default_route_ipv6] and route.gateway is not None:
                self.logger.debug('Removing route %r', route.asdict())
                try:
                    rt.delete(route)
                except Exception:
                    self.logger.exception('Failed to remove route')

        for route in new_routes:
            self.logger.debug('Adding route %r', route.asdict())
            try:
                rt.add(route)
            except Exception:
                self.logger.exception('Failed to add route')

    def _validate(self, schema_name, verrors, data):
        dst, gw = data.pop('destination'), data.pop('gateway')
        # Validate destination: CIDR notation
        try:
            dst = ip_interface(dst)
        except ValueError as ve:
            verrors.add(f'{schema_name}.destination', str(ve))

        # Validate gateway: IP address (not CIDR)
        try:
            gw = ip_address(gw)
        except ValueError as ve:
            verrors.add(f'{schema_name}.gateway', str(ve))

        if dst.version != gw.version:
            verrors.add(
                f'{schema_name}.destination',
                'Destination and gateway address families must match'
            )
        else:
            data['destination'] = dst.exploded
            data['gateway'] = gw.exploded

    def _netif_route(self, staticroute):
        ip_info = ip_interface(staticroute['destination'])
        return Route(
            str(ip_info.ip), str(ip_info.netmask), gateway=staticroute['gateway']
        )
