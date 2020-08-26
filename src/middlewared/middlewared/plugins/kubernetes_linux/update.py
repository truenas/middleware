import ipaddress
import os

import middlewared.sqlalchemy as sa

from middlewared.schema import Dict, Int, IPAddr, Str
from middlewared.service import accepts, SystemServiceService, private, ValidationErrors
from middlewared.validators import Range


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


class KubernetesService(SystemServiceService):

    class Config:
        datastore = 'services.kubernetes'
        datastore_extend = 'kubernetes.k8s_extend'
        service_model = 'kubernetes'
        service_verb = 'restart'
        service_verb_sync = False

    @private
    async def k8s_extend(self, data):
        data['dataset'] = os.path.join(data['pool'], 'ix-applications') if data['pool'] else None
        return data

    @private
    async def validate_data(self, data, schema):
        verrors = ValidationErrors()

        if not await self.middleware.call('pool.query', [['name', '=', data['pool']]]):
            verrors.add(f'{schema}.pool', 'Please provide a valid pool configured in the system.')

        if ipaddress.ip_address(data['cluster_dns_ip']) not in ipaddress.ip_network(data['service_cidr']):
            verrors.add(f'{schema}.cluster_dns_ip', 'Must be in range of "service_cidr".')

        verrors.check()

    @accepts(
        Dict(
            'kubernetes_update',
            Str('pool', empty=False),
            Int('netmask', validators=[Range(min=0, max=128)]),
            IPAddr('cluster_cidr', cidr=True),
            IPAddr('service_cidr', cidr=True),
            IPAddr('cluster_dns_ip'),
            update=True,
        )
    )
    async def do_update(self, data):
        old_config = await self.config()
        for k in ('dataset', 'cni_config'):
            old_config.pop(k)
        config = old_config.copy()
        config.update(data)

        await self.validate_data(config, 'kubernetes_update')

        if len(set(old_config.items()) ^ set(config.items())) > 0:
            await self._update_service(old_config, config)

        return await self.config()
