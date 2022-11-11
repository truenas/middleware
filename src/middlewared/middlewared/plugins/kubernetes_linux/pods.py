from aiohttp.client_exceptions import ClientConnectionError
from dateutil.parser import parse, ParserError
from kubernetes_asyncio.watch import Watch

from middlewared.event import EventSource
from middlewared.schema import Dict, Int, Str
from middlewared.service import CRUDService
from middlewared.validators import Range

from .k8s import api_client
from .k8s_base_resources import KubernetesBaseResource
from .k8s_new import Pod


class KubernetesPodService(KubernetesBaseResource, CRUDService):

    QUERY_EVENTS = True
    QUERY_EVENTS_RESOURCE_NAME = 'Pod'
    KUBERNETES_RESOURCE = Pod

    class Config:
        namespace = 'k8s.pod'
        private = True

    async def conditional_filtering_in_query(self, entry, options):
        return options['extra'].get('retrieve_all_pods') or not any(
            o['kind'] == 'DaemonSet' for o in (entry['metadata']['ownerReferences'] or [])
        )

    async def get_logs(self, pod, container, namespace, tail_lines=500, limit_bytes=None):
        # TODO: Confirm taillines/limit bytes
        return await Pod.logs(
            pod, namespace, container=container, tail_lines=tail_lines, limit_bytes=limit_bytes, timestamps=True
        )


class KubernetesPodLogsFollowTailEventSource(EventSource):

    """
    Retrieve logs of a container in a pod in a chart release.

    Name of chart release, name of pod and name of container is required.
    Optionally `tail_lines` and `limit_bytes` can be specified.

    `tail_lines` is an option to select how many lines of logs to retrieve for the said container. It
    defaults to 500. If set to `null`, it will retrieve complete logs of the container.

    `limit_bytes` is an option to select how many bytes to retrieve from the tail lines selected. If set
    to null ( which is the default ), it will not limit the bytes returned. To clarify, `tail_lines`
    is applied first and the required number of lines are retrieved and then `limit_bytes` is applied.
    """
    ACCEPTS = Dict(
        Int('tail_lines', default=500, validators=[Range(min=1)]),
        Int('limit_bytes', default=None, null=True, validators=[Range(min=1)]),
        Str('release_name', required=True),
        Str('pod_name', required=True),
        Str('container_name', required=True),
    )
    RETURNS = Dict(
        Str('data', required=True),
        Str('timestamp', required=True, null=True)
    )

    def __init__(self, *args, **kwargs):
        super(KubernetesPodLogsFollowTailEventSource, self).__init__(*args, **kwargs)
        self.watch = None

    async def run(self):
        release = self.arg['release_name']
        pod = self.arg['pod_name']
        container = self.arg['container_name']
        tail_lines = self.arg['tail_lines']
        limit_bytes = self.arg['limit_bytes']

        await self.middleware.call('chart.release.validate_pod_log_args', release, pod, container)
        release_data = await self.middleware.call('chart.release.get_instance', release)

        async with api_client() as (api, context):
            self.watch = Watch()
            try:
                async with self.watch.stream(
                    context['core_api'].read_namespaced_pod_log, name=pod, container=container,
                    namespace=release_data['namespace'], tail_lines=tail_lines, limit_bytes=limit_bytes,
                    timestamps=True, _request_timeout=1800
                ) as stream:
                    async for event in stream:
                        # Event should contain a timestamp in RFC3339 format, we should parse it and supply it
                        # separately so UI can highlight the timestamp giving us a cleaner view of the logs
                        timestamp = event.split(maxsplit=1)[0].strip()
                        try:
                            timestamp = str(parse(timestamp))
                        except (TypeError, ParserError):
                            timestamp = None
                        else:
                            event = event.split(maxsplit=1)[-1].lstrip()

                        self.send_event('ADDED', fields={'data': event, 'timestamp': timestamp})
            except ClientConnectionError:
                pass

    async def cancel(self):
        await super().cancel()
        if self.watch:
            await self.watch.close()

    async def on_finish(self):
        self.watch = None


def setup(middleware):
    middleware.register_event_source('kubernetes.pod_log_follow', KubernetesPodLogsFollowTailEventSource)
