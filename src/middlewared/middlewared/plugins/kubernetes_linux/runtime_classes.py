from middlewared.schema import accepts, Dict, List, Str
from middlewared.service import CallError, CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import ApiException, RuntimeClass


class KubernetesRuntimeClassService(CRUDService):

    class Config:
        namespace = 'k8s.runtime_class'
        private = True

    @filterable
    async def query(self, filters, options):
        return filter_list((await RuntimeClass.query())['items'], filters, options)

    @accepts(
        Dict(
            'runtime_class_create',
            Dict('body', additional_attrs=True, required=True),
        )
    )
    async def do_create(self, data):
        try:
            await RuntimeClass.create(data['body'])
        except ApiException as e:
            raise CallError(f'Failed to create runtime class: {e}')

    @accepts(Str('runtime_class_name'))
    async def do_delete(self, runtime_class_name):
        try:
            await RuntimeClass.delete(runtime_class_name)
        except ApiException as e:
            raise CallError(f'Failed to delete {runtime_class_name!r} runtime class: {e}')
