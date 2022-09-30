import asyncio
import ipaddress
import itertools

import middlewared.sqlalchemy as sa

from middlewared.common.listen import ConfigServiceListenSingleDelegate
from middlewared.schema import Bool, Dict, Int, IPAddr, Patch, returns, Str
from middlewared.service import accepts, CallError, job, private, ConfigService, ValidationErrors

from .k8s import api_client
from .utils import applications_ds_name


class KubernetesModel(sa.Model):
    __tablename__ = 'services_kubernetes'

    id = sa.Column(sa.Integer(), primary_key=True)
    pool = sa.Column(sa.String(255), default=None, nullable=True)
    cluster_cidr = sa.Column(sa.String(128), default='')
    service_cidr = sa.Column(sa.String(128), default='')
    cluster_dns_ip = sa.Column(sa.String(128), default='')
    route_v4_interface = sa.Column(sa.String(128), nullable=True)
    route_v4_gateway = sa.Column(sa.String(128), nullable=True)
    route_v6_interface = sa.Column(sa.String(128), nullable=True)
    route_v6_gateway = sa.Column(sa.String(128), nullable=True)
    node_ip = sa.Column(sa.String(128), default='0.0.0.0')
    cni_config = sa.Column(sa.JSON(type=dict), default={})
    configure_gpus = sa.Column(sa.Boolean(), default=True, nullable=False)
    servicelb = sa.Column(sa.Boolean(), default=True, nullable=False)
    validate_host_path = sa.Column(sa.Boolean(), default=True)


class KubernetesService(ConfigService):

    class Config:
        datastore = 'services.kubernetes'
        datastore_extend = 'kubernetes.k8s_extend'
        cli_namespace = 'app.kubernetes'

    ENTRY = Dict(
        'kubernetes_entry',
        Bool('servicelb', required=True),
        Bool('configure_gpus', required=True),
        Bool('validate_host_path', required=True),
        Str('pool', required=True, null=True),
        IPAddr('cluster_cidr', required=True, cidr=True, empty=True),
        IPAddr('service_cidr', required=True, cidr=True, empty=True),
        IPAddr('cluster_dns_ip', required=True, empty=True),
        IPAddr('node_ip', required=True),
        Str('route_v4_interface', required=True, null=True),
        IPAddr('route_v4_gateway', required=True, null=True, v6=False),
        Str('route_v6_interface', required=True, null=True),
        IPAddr('route_v6_gateway', required=True, null=True, v4=False),
        Str('dataset', required=True, null=True),
        Int('id', required=True),
        update=True,
    )

    @private
    async def k8s_extend(self, data):
        data['dataset'] = applications_ds_name(data['pool']) if data['pool'] else None
        data.pop('cni_config')
        return data

    @private
    async def unused_cidrs(self, network_cidrs):
        return [
            str(network) for network in itertools.chain(
                ipaddress.ip_network('172.16.0.0/12', False).subnets(4),
                ipaddress.ip_network('10.0.0.0/8', False).subnets(8),
                ipaddress.ip_network('192.168.0.0/16', False).subnets(1),
            ) if not any(network.overlaps(used_network) for used_network in network_cidrs)
        ]

    @private
    async def licensed_for_apps(self):
        can_run_apps = True
        if await self.middleware.call('system.is_ha_capable'):
            license = await self.middleware.call('system.license')
            can_run_apps = license is not None and 'JAILS' in license['features']

        return can_run_apps

    @private
    async def validate_data(self, data, schema, old_data):
        verrors = ValidationErrors()

        if await self.middleware.call('system.is_ha_capable') and 'JAILS' not in (await self.middleware.call(
            'system.license'
        ))['features']:
            verrors.add(
                f'{schema}.pool',
                'System is not licensed to use Applications'
            )

        if data.pop('migrate_applications', False):
            if data['pool'] == old_data['pool']:
                verrors.add(
                    f'{schema}.migrate_applications',
                    'Migration of applications dataset only happens when a new pool is configured.'
                )
            elif not data['pool']:
                verrors.add(
                    f'{schema}.migrate_applications',
                    'Pool must be specified when migration of ix-application dataset is desired.'
                )
            elif not old_data['pool']:
                verrors.add(
                    f'{schema}.migrate_applications',
                    'A pool must have been configured previously for ix-application dataset migration.'
                )
            else:
                if await self.middleware.call(
                    'zfs.dataset.query', [['id', '=', applications_ds_name(data['pool'])]], {
                        'extra': {'retrieve_children': False, 'retrieve_properties': False}
                    }
                ):
                    verrors.add(
                        f'{schema}.migrate_applications',
                        f'Migration of {applications_ds_name(old_data["pool"])!r} to {data["pool"]!r} not '
                        f'possible as {applications_ds_name(data["pool"])} already exists.'
                    )

                if not await self.middleware.call(
                    'zfs.dataset.query', [['id', '=', applications_ds_name(old_data['pool'])]], {
                        'extra': {'retrieve_children': False, 'retrieve_properties': False}
                    }
                ):
                    # Edge case but handled just to be sure
                    verrors.add(
                        f'{schema}.migrate_applications',
                        f'{applications_ds_name(old_data["pool"])!r} does not exist, migration not possible.'
                    )

        network_cidrs = set([
            ipaddress.ip_network(f'{ip_config["address"]}/{ip_config["netmask"]}', False)
            for interface in await self.middleware.call('interface.query')
            for ip_config in itertools.chain(interface['aliases'], interface['state']['aliases'])
            if ip_config['type'] != 'LINK'
        ])

        unused_cidrs = []
        if not data['cluster_cidr'] or not data['service_cidr']:
            unused_cidrs = await self.unused_cidrs(network_cidrs)
            # If index 0,1 belong to different classes, let's make sure that is not the case anymore
            if len(unused_cidrs) > 2 and unused_cidrs[0].split('.')[0] != unused_cidrs[1].split('.')[0]:
                unused_cidrs.pop(0)

        if unused_cidrs and not data['cluster_cidr']:
            data['cluster_cidr'] = unused_cidrs.pop(0)

        if unused_cidrs and not data['service_cidr']:
            data['service_cidr'] = unused_cidrs.pop(0)

        if not data['cluster_dns_ip']:
            if data['service_cidr']:
                # Picking 10th ip ( which is the usual default ) from service cidr
                data['cluster_dns_ip'] = str(list(ipaddress.ip_network(data['service_cidr'], False).hosts())[9])
            else:
                verrors.add(f'{schema}.cluster_dns_ip', 'Please specify cluster_dns_ip.')

        if data['pool'] and not await self.middleware.call('pool.query', [['name', '=', data['pool']]]):
            verrors.add(f'{schema}.pool', 'Please provide a valid pool configured in the system.')

        for k in ('cluster_cidr', 'service_cidr'):
            if not data[k]:
                verrors.add(f'{schema}.{k}', f'Please specify a {k.split("_")[0]} CIDR.')
            elif any(ipaddress.ip_network(data[k], False).overlaps(cidr) for cidr in network_cidrs):
                verrors.add(f'{schema}.{k}', 'Requested CIDR is already in use.')

        if data['cluster_cidr'] and data['service_cidr'] and ipaddress.ip_network(data['cluster_cidr'], False).overlaps(
            ipaddress.ip_network(data['service_cidr'], False)
        ):
            verrors.add(f'{schema}.cluster_cidr', 'Must not overlap with service CIDR.')

        if data['service_cidr'] and data['cluster_dns_ip'] and ipaddress.ip_address(
            data['cluster_dns_ip']
        ) not in ipaddress.ip_network(data['service_cidr']):
            verrors.add(f'{schema}.cluster_dns_ip', 'Must be in range of "service_cidr".')

        if data['node_ip'] not in await self.bindip_choices():
            verrors.add(f'{schema}.node_ip', 'Please provide a valid IP address.')

        if not await self.middleware.call('route.configured_default_ipv4_route'):
            verrors.add(
                f'{schema}.route_v4_interface',
                'Please, set IPv4 Default Gateway (it can be fake) in Network → Global Configuration and then '
                'update Kubernetes settings. Currently, k3s cannot be used without a default route.'
            )

        valid_choices = await self.route_interface_choices()
        for k, _ in await self.validate_interfaces(data):
            verrors.add(f'{schema}.{k}', f'Please specify a valid interface (i.e {", ".join(valid_choices)!r}).')

        for k in ('route_v4', 'route_v6'):
            gateway = data[f'{k}_gateway']
            interface = data[f'{k}_interface']
            if (not gateway and not interface) or (gateway and interface):
                continue
            for k2 in ('gateway', 'interface'):
                verrors.add(f'{schema}.{k}_{k2}', f'{k}_gateway and {k}_interface must be specified together.')

        if data['route_v4_gateway']:
            gateway = ipaddress.ip_address(data['route_v4_gateway'])
            if not any(gateway in network_cidr for network_cidr in network_cidrs):
                verrors.add(
                    f'{schema}.route_v4_gateway',
                    'Specified value is not present on any network cidr in use by the system'
                )

        if not data['validate_host_path'] and await self.middleware.call('failover.hardware') != 'MANUAL':
            verrors.add(
                f'{schema}.validate_host_path',
                'Host path validation cannot be switched off for SCALE ENTERPRISE users'
            )

        verrors.check()

    @private
    async def validate_interfaces(self, data):
        errors = []
        interfaces = await self.route_interface_choices()
        for k in filter(
            lambda k: data[k] and data[k] not in interfaces, ('route_v4_interface', 'route_v6_interface')
        ):
            errors.append((k, data[k]))
        return errors

    @private
    async def validate_config(self):
        data = await self.middleware.call('kubernetes.config')
        data.pop('id')
        data.pop('dataset')

        try:
            await self.validate_data(data, 'kubernetes', data)
        except ValidationErrors as e:
            return e

    @accepts(
        Patch(
            'kubernetes_entry', 'kubernetes_update',
            ('add', Bool('migrate_applications')),
            ('rm', {'name': 'id'}),
            ('rm', {'name': 'dataset'}),
            ('attr', {'update': True}),
        )
    )
    @job(lock='kubernetes_update')
    async def do_update(self, job, data):
        """
        `pool` must be a valid ZFS pool configured in the system. Kubernetes service will initialise the pool by
        creating datasets under `pool_name/ix-applications`.

        `configure_gpus` is a boolean to enable or disable to prevent automatically loading any GPU Support
        into kubernetes. This includes not loading any daemonsets for Intel and NVIDIA support.

        `servicelb` is a boolean to enable or disable the integrated k3s Service Loadbalancer called "Klipper".
        This can be set to disabled to enable the user to run another LoadBalancer or no LoadBalancer at all.

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
        for default NAT network.

        By default kubernetes pods will be using default gateway of the system for outward traffic. This might
        not be desirable for certain users who want to separate NAT traffic over a specific interface / route. System
        will create a L3 network which will be routing the traffic towards default gateway for NAT.

        If users want to restrict traffic over a certain gateway / interface, they can specify a default route
        for the NAT traffic. `route_v4_interface` and `route_v4_gateway` will set a default route for the kubernetes
        cluster IPv4 traffic. Similarly `route_v6_interface` and 'route_v6_gateway` can be used to specify default
        route for IPv6 traffic.

        In case user is switching pools and the new desired pool has not been configured for kubernetes before, it
        is possible to replicate data from old pool to new pool with setting `migrate_applications` attribute. This
        will replicate contents of old pool's ix-applications dataset to the new pool.
        """
        old_config = await self.config()
        old_config.pop('dataset')
        config = old_config.copy()
        config.update(data)
        migrate = config.get('migrate_applications')

        await self.validate_data(config, 'kubernetes_update', old_config)

        if len(set(old_config.items()) ^ set(config.items())) > 0:
            await self.middleware.call('chart.release.clear_update_alerts_for_all_chart_releases')
            if migrate and config['pool'] != old_config['pool']:
                job.set_progress(
                    25,
                    f'Migrating {applications_ds_name(old_config["pool"])} to {applications_ds_name(config["pool"])}'
                )
                await self.middleware.call(
                    'kubernetes.migrate_ix_applications_dataset', job, config, old_config
                )
                job.set_progress(100, 'Migration complete for ix-applications dataset')
            else:
                config['cni_config'] = {}
                await self.middleware.call('datastore.update', self._config.datastore, old_config['id'], config)
                await self.middleware.call('kubernetes.status_change')
                if not config['pool'] and config['pool'] != old_config['pool']:
                    # We only want to do this when we don't have any pool configured and would like to use
                    # host catalog repos temporarily. Otherwise, we should call this after k8s datasets have
                    # been initialised
                    await self.middleware.call('catalog.sync_all')

        return await self.config()

    @accepts()
    @returns(Dict('kubernetes_bind_ip_choices', additional_attrs=True,))
    async def bindip_choices(self):
        """
        Returns ip choices for Kubernetes service to use.
        """
        return {
            d['address']: d['address'] for d in await self.middleware.call(
                'interface.ip_in_use', {'static': True, 'any': True, 'ipv6': False}
            )
        }

    @accepts()
    @returns(Dict(additional_attrs=True))
    async def route_interface_choices(self):
        """
        Returns Interface choices for Kubernetes service to use for ipv4 connections.
        """
        return await self.middleware.call(
            'interface.choices', {'bridge_members': False, 'lag_ports': False}
        )

    @private
    async def validate_k8s_setup(self, raise_exception=True):
        error = None
        k8s_config = await self.middleware.call('kubernetes.config')
        if not k8s_config['dataset']:
            error = 'Please configure kubernetes pool.'
        if not error and not await self.middleware.call('service.started', 'kubernetes'):
            error = 'Kubernetes service is not running.'

        if not error:
            try:
                async with api_client({'node': True}, {'request_timeout': 2}) as (api, context):
                    pass
            except asyncio.exceptions.TimeoutError:
                error = 'Unable to connect to kubernetes cluster'

        if error and raise_exception:
            raise CallError(error)
        return not error

    @accepts()
    @returns(Str('kubernetes_node_ip', null=True))
    async def node_ip(self):
        """
        Returns IP used by kubernetes which kubernetes uses to allow incoming connections.
        """
        node_ip = None
        if await self.validate_k8s_setup(False):
            k8s_node_config = await self.middleware.call('k8s.node.config')
            if k8s_node_config['node_configured']:
                node_ip = next((
                    addr['address'] for addr in k8s_node_config['status']['addresses'] if addr['type'] == 'InternalIP'
                ), None)
        if not node_ip:
            node_ip = (await self.middleware.call('kubernetes.config'))['node_ip']

        return node_ip


async def setup(middleware):
    await middleware.call(
        'interface.register_listen_delegate',
        ConfigServiceListenSingleDelegate(middleware, 'kubernetes', 'node_ip'),
    )
