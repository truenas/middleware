import ipaddress
import os

import middlewared.sqlalchemy as sa

from middlewared.schema import Dict, IPAddr, Str
from middlewared.service import accepts, job, private, ConfigService, ValidationErrors


class KubernetesModel(sa.Model):
    __tablename__ = 'services_kubernetes'

    id = sa.Column(sa.Integer(), primary_key=True)
    pool = sa.Column(sa.String(255), default=None, nullable=True)
    cluster_cidr = sa.Column(sa.String(128), default='172.16.0.0/16')
    service_cidr = sa.Column(sa.String(128), default='172.17.0.0/16')
    cluster_dns_ip = sa.Column(sa.String(128), default='172.17.0.10')
    route_v4 = sa.Column(sa.JSON(type=dict))
    route_v6 = sa.Column(sa.JSON(type=dict))
    node_ip = sa.Column(sa.String(128), default='0.0.0.0')
    cni_config = sa.Column(sa.JSON(type=dict))


class KubernetesService(ConfigService):

    class Config:
        datastore = 'services.kubernetes'
        datastore_extend = 'kubernetes.k8s_extend'

    @private
    async def k8s_extend(self, data):
        data['dataset'] = os.path.join(data['pool'], 'ix-applications') if data['pool'] else None
        data.pop('cni_config')
        return data

    @private
    async def validate_data(self, data, schema):
        verrors = ValidationErrors()

        if data['pool'] and not await self.middleware.call('pool.query', [['name', '=', data['pool']]]):
            verrors.add(f'{schema}.pool', 'Please provide a valid pool configured in the system.')

        if ipaddress.ip_address(data['cluster_dns_ip']) not in ipaddress.ip_network(data['service_cidr']):
            verrors.add(f'{schema}.cluster_dns_ip', 'Must be in range of "service_cidr".')

        if data['node_ip'] not in await self.bindip_choices():
            verrors.add(f'{schema}.node_ip', 'Please provide a valid IP address.')

        interfaces = {i['name']: i for i in await self.middleware.call('interface.query')}
        for k in filter(
            lambda k: k in data and data[k]['interface'] not in interfaces, ('route_v4', 'route_v6')
        ):
            verrors.add(f'{schema}.{k}.interface', 'Please specify a valid interface.')

        verrors.check()

    @accepts(
        Dict(
            'kubernetes_update',
            Str('pool', empty=False, null=True),
            IPAddr('cluster_cidr', cidr=True),
            IPAddr('service_cidr', cidr=True),
            IPAddr('cluster_dns_ip'),
            IPAddr('node_ip'),
            Dict(
                'route_v4',
                Str('interface', required=True),
                IPAddr('gateway', required=True, v6=False),
            ),
            Dict(
                'route_v6',
                Str('interface', required=True),
                IPAddr('gateway', required=True, v4=False),
            ),
            update=True,
        )
    )
    @job(lock='kubernetes_update')
    async def do_update(self, job, data):
        """
        `pool` must be a valid ZFS pool configured in the system. Kubernetes service will initialise the pool by
        creating datasets under `pool_name/ix-applications`.

        `cluster_cidr` is the CIDR to be used for default NAT network between workloads.

        `service_cidr` is the CIDR to be used for kubernetes services which are an abstraction and refer to a
        logically set of kubernetes pods.

        `cluster_dns_ip` is the IP of the DNS server running for the kubernetes cluster. It must be in the range
        of `service_cidr`.

        Specifying values for `cluster_cidr`, `service_cidr` and `cluster_dns_ip` are permanent and a subsequent change
        requires re-initialisation of the applications. To clarify, system will destroy old `ix-applications` dataset
        and any data within it when any of the values for the above configuration change.

        `node_ip` is the IP address which the kubernetes cluster will assign to the TrueNAS node. It defaults to
        0.0.0.0 and the cluster in this case will automatically manage which IP address to use for managing traffic
        for default NAT network. If it is desired that traffic uses a certain interface / ip address, that IP address
        can be specified and the NAT network will use related IP address and it's routes to manage the traffic.
        """
        old_config = await self.config()
        for k in ('dataset', 'route_v4', 'route_v6'):
            old_config.pop(k)
        config = old_config.copy()
        config.update(data)

        await self.validate_data(config, 'kubernetes_update')

        route_v4 = config.pop('route_v4', None)
        route_v6 = config.pop('route_v6', None)
        if len(set(old_config.items()) ^ set(config.items())) > 0:
            config['cni_config'] = {}
            if route_v4:
                config['route_v4'] = route_v4
            if route_v6:
                config['route_v6'] = route_v6
            await self.middleware.call('datastore.update', self._config.datastore, old_config['id'], config)
            await self.middleware.call('kubernetes.status_change')

        return await self.config()

    @accepts()
    async def bindip_choices(self):
        """
        Returns ip choices for Kubernetes service to use.
        """
        return {
            d['address']: d['address'] for d in await self.middleware.call(
                'interface.ip_in_use', {'static': True, 'any': True}
            )
        }
