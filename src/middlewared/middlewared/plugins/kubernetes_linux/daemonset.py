from kubernetes_asyncio import client

from middlewared.schema import Dict, Ref, Str
from middlewared.service import accepts, CallError, CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client
from .k8s_new import ApiException, DaemonSet


class KubernetesDaemonsetService(CRUDService):

    class Config:
        namespace = 'k8s.daemonset'
        private = True

    @filterable
    async def query(self, filters, options):
        return filter_list((await DaemonSet.query())['items'], filters, options)

    @accepts(
        Dict(
            'daemonset_create',
            Str('namespace', required=True),
            Dict('body', additional_attrs=True, required=True),
            register=True
        )
    )
    async def do_create(self, data):
        try:
            await DaemonSet.create(data['body'], namespace=data['namespace'])
        except ApiException as e:
            raise CallError(f'Unable to create daemonset: {e}')

    @accepts(
        Str('name'),
        Ref('daemonset_create'),
    )
    async def do_update(self, name, data):
        try:
            await DaemonSet.update(name, data['body'], namespace=data['namespace'])
        except ApiException as e:
            raise CallError(f'Unable to update daemonset: {e}')

    @accepts(
        Str('name'),
        Dict(
            'daemonset_delete_options',
            Str('namespace', required=True),
        )
    )
    async def do_delete(self, name, options):
        try:
            await DaemonSet.delete(name, **options)
        except ApiException as e:
            raise CallError(f'Unable to delete daemonset: {e}')
