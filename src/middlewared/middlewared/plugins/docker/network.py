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
        Str('id', required=True),
        Str('name', required=True),
        Str('short_id', required=True),
        additional_attrs=True,
    )

    @filterable
    def query(self, filters, options):
        """
        Query all docker networks
        """
        if not self.middleware.call_sync('docker.state.validate', False):
            return filter_list([], filters, options)

        return filter_list(list_networks(), filters, options)
