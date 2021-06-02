from kubernetes_asyncio import client

from middlewared.schema import Dict, Ref, Str
from middlewared.service import accepts, CallError, CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client


class KubernetesJobService(CRUDService):

    class Config:
        namespace = 'k8s.job'
        private = True

    @filterable
    async def query(self, filters, options):
        async with api_client() as (api, context):
            return filter_list(
                [d.to_dict() for d in (await context['batch_api'].list_job_for_all_namespaces()).items],
                filters, options
            )

    @accepts(
        Dict(
            'k8s_job_create',
            Str('namespace', required=True),
            Dict('body', additional_attrs=True, required=True),
            register=True
        )
    )
    async def do_create(self, data):
        async with api_client() as (api, context):
            try:
                await context['batch_api'].create_namespaced_job(namespace=data['namespace'], body=data['body'])
            except client.exceptions.ApiException as e:
                raise CallError(f'Unable to create job: {e}')
            else:
                return await self.query([
                    ['metadata.name', '=', data['metadata.name']],
                    ['metadata.namespace', '=', data['namespace']],
                ], {'get': True})

    @accepts(
        Str('name'),
        Ref('k8s_job_create'),
    )
    async def do_update(self, name, data):
        async with api_client() as (api, context):
            try:
                await context['batch_api'].patch_namespaced_job(
                    name, namespace=data['namespace'], body=data['body']
                )
            except client.exceptions.ApiException as e:
                raise CallError(f'Unable to patch {name} job: {e}')
            else:
                return await self.query([
                    ['metadata.name', '=', name],
                    ['metadata.namespace', '=', data['namespace']],
                ], {'get': True})

    @accepts(
        Str('name'),
        Dict(
            'k8s_job_delete_options',
            Str('namespace', required=True),
        )
    )
    async def do_delete(self, name, options):
        async with api_client() as (api, context):
            try:
                await context['batch_api'].delete_namespaced_job(name, options['namespace'])
            except client.exceptions.ApiException as e:
                raise CallError(f'Unable to delete job: {e}')
            else:
                return True


class KubernetesCronJobService(CRUDService):

    class Config:
        namespace = 'k8s.cronjob'
        private = True

    @filterable
    async def query(self, filters, options):
        async with api_client() as (api, context):
            return filter_list(
                [d.to_dict() for d in (await context['cronjob_batch_api'].list_cron_job_for_all_namespaces()).items],
                filters, options
            )

    @accepts(Ref('k8s_job_create'))
    async def do_create(self, data):
        async with api_client() as (api, context):
            try:
                await context['cronjob_batch_api'].create_namespaced_cron_job(
                    namespace=data['namespace'], body=data['body']
                )
            except client.exceptions.ApiException as e:
                raise CallError(f'Unable to create job: {e}')
            else:
                return await self.query([
                    ['metadata.name', '=', data['metadata.name']],
                    ['metadata.namespace', '=', data['namespace']],
                ], {'get': True})

    @accepts(
        Str('name'),
        Ref('k8s_job_create'),
    )
    async def do_update(self, name, data):
        async with api_client() as (api, context):
            try:
                await context['cronjob_batch_api'].patch_namespaced_cron_job(
                    name, namespace=data['namespace'], body=data['body']
                )
            except client.exceptions.ApiException as e:
                raise CallError(f'Unable to patch {name} job: {e}')
            else:
                return await self.query([
                    ['metadata.name', '=', name],
                    ['metadata.namespace', '=', data['namespace']],
                ], {'get': True})

    @accepts(
        Str('name'),
        Dict(
            'k8s_job_delete_options',
            Str('namespace', required=True),
        )
    )
    async def do_delete(self, name, options):
        async with api_client() as (api, context):
            try:
                await context['cronjob_batch_api'].delete_namespaced_cron_job(name, options['namespace'])
            except client.exceptions.ApiException as e:
                raise CallError(f'Unable to delete job: {e}')
            else:
                return True
