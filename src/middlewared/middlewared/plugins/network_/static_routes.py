from ipaddress import ip_interface

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
from middlewared.service_exception import ValidationError
from middlewared.plugins.interface.netif import netif


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

    @api_method(StaticRouteCreateArgs, StaticRouteCreateResult)
    async def do_create(self, data):
        """
        Create a Static Route.

        Address families of `gateway` and `destination` should match when creating a static route.

        `description` is an optional attribute for any notes regarding the static route.
        """
        self._validate('staticroute_create', data)

        id_ = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self.middleware.call('service.restart', 'routing')

        return await self.get_instance(id_)

    @api_method(StaticRouteUpdateArgs, StaticRouteUpdateResult)
    async def do_update(self, id_, data):
        """
        Update Static Route of `id`.
        """
        old = await self.get_instance(id_)
        new = old.copy()
        new.update(data)

        self._validate('staticroute_update', new)

        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix})

        await self.middleware.call('service.restart', 'routing')

        return await self.get_instance(id_)

    @api_method(StaticRouteDeleteArgs, StaticRouteDeleteResult)
    def do_delete(self, id_):
        """
        Delete Static Route of `id`.
        """
        st = self.middleware.call_sync('staticroute.get_instance', id_)
        rv = self.middleware.call_sync('datastore.delete', self._config.datastore, id_)
        try:
            rt = netif.RoutingTable()
            rt.delete(self._netif_route(st))
        except Exception:
            self.logger.exception('Failed to delete static route %r', st['destination'])

        return rv

    @private
    def sync(self):
        new_routes = list()
        for route in self.middleware.call_sync('staticroute.query'):
            new_routes.append(self._netif_route(route))

        rt = netif.RoutingTable()
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

    def _validate(self, schema_name, data):
        dst, gw = data.pop('destination'), data.pop('gateway')
        dst, gw = ip_interface(dst), ip_interface(gw)
        if dst.version != gw.version:
            raise ValidationError(
                f'{schema_name}.destination',
                'Destination and gateway address families must match'
            )
        else:
            data['destination'] = dst.exploded
            data['gateway'] = gw.ip.exploded

    def _netif_route(self, staticroute):
        ip_info = ip_interface(staticroute['destination'])
        return netif.Route(
            str(ip_info.ip), str(ip_info.netmask), gateway=staticroute['gateway']
        )
