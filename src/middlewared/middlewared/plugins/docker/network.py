from middlewared.api.current import DockerNetworkEntry
from middlewared.plugins.apps.ix_apps.docker.networks import list_networks
from middlewared.service import CRUDService, private
from middlewared.utils.filter_list import filter_list


class DockerNetworkService(CRUDService):

    class Config:
        namespace = 'docker.network'
        datastore_primary_key_type = 'string'
        cli_namespace = 'docker.network'
        role_prefix = 'DOCKER'
        entry = DockerNetworkEntry

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

    @private
    def interfaces_mapping(self):
        try:
            return [f'br-{network["short_id"]}' for network in self.query()]
        except Exception as e:
            # We don't want this to fail ever because this is used in interface.sync
            self.logger.error('Failed to get docker interfaces mapping: %s', e)
            return []
