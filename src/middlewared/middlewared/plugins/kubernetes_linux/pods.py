from kubernetes_asyncio.watch import Watch

from middlewared.main import EventSource
from middlewared.service import CallError, CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client


class KubernetesPodService(CRUDService):

    class Config:
        namespace = 'k8s.pod'
        private = True

    @filterable
    async def query(self, filters, options):
        options = options or {}
        label_selector = options.get('extra', {}).get('label_selector')
        kwargs = {k: v for k, v in [('label_selector', label_selector)] if v}
        async with api_client() as (api, context):
            pods = [d.to_dict() for d in (await context['core_api'].list_pod_for_all_namespaces(**kwargs)).items]
            events = await self.middleware.call(
                'kubernetes.get_events_of_resource_type', 'Pod', [p['metadata']['uid'] for p in pods]
            )

            for pod in pods:
                pod['events'] = events[pod['metadata']['uid']]

        return filter_list(pods, filters, options)

    async def get_logs(self, pod, container, namespace):
        async with api_client() as (api, context):
            return await context['core_api'].read_namespaced_pod_log(
                name=pod, container=container, namespace=namespace
            )


class KubernetesPodLogsFileFollowTailEventSource(EventSource):

    """
    Retrieve logs of a container in a pod in a chart release.

    Name of chart release, name of pod and name of container is required.
    Format is "release-name_pod-name_container-name", each parameter is separated by `_`.
    """

    async def run(self):
        if str(self.arg).count('_') < 2:
            raise CallError('Arguments in the format "release-name_pod-name_container-name" must be specified.')

        release, pod, container = self.arg.split('_', 2)
        await self.middleware.call('chart.release.validate_pod_log_args', release, pod, container)
        release_data = await self.middleware.call('chart.release.get_instance', release)

        async with api_client() as (api, context):
            async with Watch().stream(
                context['core_api'].read_namespaced_pod_log, name=pod, container=container,
                namespace=release_data['namespace'],
            ) as stream:
                async for event in stream:
                    if self._cancel.is_set():
                        return
                    self.send_event('ADDED', fields={'data': event})


def setup(middleware):
    middleware.register_event_source('kubernetes.pod_log_follow', KubernetesPodLogsFileFollowTailEventSource)
