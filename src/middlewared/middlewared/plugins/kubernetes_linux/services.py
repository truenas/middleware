from middlewared.service import accepts, CRUDService, filterable
from middlewared.schema import Dict, Str
from middlewared.utils import filter_list

from .k8s_new import Service


class KubernetesServicesService(CRUDService):

    class Config:
        namespace = 'k8s.service'
        private = True

    @filterable
    async def query(self, filters, options):
        return filter_list((await Service.query())['items'], filters, options)

    @accepts(
        Str('name'),
        Dict(
            'service_delete_options',
            Str('namespace', required=True),
        )
    )
    async def do_delete(self, name, options):
        await Service.delete(name, **options)
