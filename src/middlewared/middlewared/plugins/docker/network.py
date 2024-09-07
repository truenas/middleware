from middlewared.plugins.apps.ix_apps.docker.networks import list_networks
from middlewared.schema import Dict, Str
from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list


class DockerNetworkService(CRUDService):

    class Config:
        namespace = 'docker.network'
        datastore_primary_key_type = 'string'
        cli_namespace = 'docker.network'
        role_prefix = 'DOCKER'

    ENTRY = Dict(
        'docker_network_entry',
        Dict('ipam', additional_attrs=True, null=True),
        Dict('labels', additional_attrs=True, null=True),
        Str('created', required=True, null=True),
        Str('driver', required=True, null=True),
        Str('id', required=True, null=True),
        Str('name', required=True, null=True),
        Str('scope', required=True, null=True),
        Str('short_id', required=True, null=True),
        additional_attrs=True,
    )

    @filterable
    def query(self, filters, options):
        """
        Query all docker networks
        """
        if not self.middleware.call_sync('docker.state.validate', False):
            return filter_list([], filters, options)

        networks = []
        for network in list_networks():
            networks.append({
                k: network.get(k) for k in (
                    'ipam', 'labels', 'created', 'driver', 'id', 'name', 'scope', 'short_id',
                )
            })

        return filter_list(networks, filters, options)
