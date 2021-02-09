import json

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

    async def get_logs(self, pod, container, namespace, tail_lines=500, limit_bytes=None):
        async with api_client() as (api, context):
            return await context['core_api'].read_namespaced_pod_log(
                name=pod, container=container, namespace=namespace, tail_lines=tail_lines, limit_bytes=limit_bytes,
            )


class KubernetesPodLogsFileFollowTailEventSource(EventSource):

    """
    Retrieve logs of a container in a pod in a chart release.

    Name of chart release, name of pod and name of container is required.
    Format is "release-name_pod-name_container-name", each parameter is separated by `_`.
    """

    def __init__(self, *args, **kwargs):
        super(KubernetesPodLogsFileFollowTailEventSource, self).__init__(*args, **kwargs)
        self.watch = None

    async def run(self):
        options = {}
        if self.arg:
            options = json.loads(self.arg)

        release = options.get('release_name')
        pod = options.get('pod_name')
        container = options.get('container_name')
        tail_lines = options.get('tail_lines', 1000)
        limit_bytes = options.get('limit_bytes')

        await self.middleware.call('chart.release.validate_pod_log_args', release, pod, container)
        if not tail_lines or tail_lines < 1:
            raise CallError('Tail lines must be greater then 0.')
        elif limit_bytes is not None and limit_bytes < 1:
            raise CallError('Limit bytes must be null or greater then 0.')

        release_data = await self.middleware.call('chart.release.get_instance', release)

        async with api_client() as (api, context):
            self.watch = Watch()
            async with self.watch.stream(
                context['core_api'].read_namespaced_pod_log, name=pod, container=container,
                namespace=release_data['namespace'], tail_lines=tail_lines, limit_bytes=limit_bytes,
            ) as stream:
                async for event in stream:
                    self.send_event('ADDED', fields={'data': event})

    async def cancel(self):
        await super().cancel()
        if self.watch:
            self.watch.close()

    async def on_finish(self):
        self.watch = None


def setup(middleware):
    middleware.register_event_source('kubernetes.pod_log_follow', KubernetesPodLogsFileFollowTailEventSource)
