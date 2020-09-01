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
    route_configuration = sa.Column(sa.JSON(type=dict))
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

        verrors.check()

    @accepts(
        Dict(
            'kubernetes_update',
            Str('pool', empty=False, null=True),
            IPAddr('cluster_cidr', cidr=True),
            IPAddr('service_cidr', cidr=True),
            IPAddr('cluster_dns_ip'),
            IPAddr('node_ip'),
            update=True,
        )
    )
    @job(lock='kubernetes_update')
    async def do_update(self, job, data):
        old_config = await self.config()
        old_config.pop('dataset')
        config = old_config.copy()
        config.update(data)

        await self.validate_data(config, 'kubernetes_update')

        if len(set(old_config.items()) ^ set(config.items())) > 0:
            config['cni_config'] = {}
            await self.middleware.call('datastore.update', self._config.datastore, old_config['id'], config)
            await self.middleware.call('kubernetes.status_change')

        return await self.config()

    @accepts()
    async def bindip_choices(self):
        """
        Returns ip choices for Kubernetes service to use
        """
        return {
            d['address']: d['address'] for d in await self.middleware.call(
                'interface.ip_in_use', {'static': True, 'any': True}
            )
        }
