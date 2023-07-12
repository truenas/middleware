from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import Node


class KubernetesStatsService(CRUDService):

    class Config:
        namespace = 'k8s.stats'
        private = True

    @filterable
    async def summary(self, filters, options):
        """
        Retrieve summary of kubernetes cluster.
        """
        return filter_list((await Node.get_stats())['pods'], filters, options)
