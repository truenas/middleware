import errno

from middlewared.schema import Dict, Int, Str
from middlewared.service import accepts, CallError, job, private, Service
from middlewared.validators import Range

from .utils import get_namespace


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def retrieve_pod_with_containers(self, release_name):
        await self.middleware.call('kubernetes.validate_k8s_setup')
        release = await self.middleware.call(
            'chart.release.query', [['id', '=', release_name]], {'get': True, 'extra': {'retrieve_resources': True}}
        )
        choices = {}
        for pod in release['resources']['pods']:
            choices[pod['metadata']['name']] = []
            for container in pod['status']['container_statuses']:
                choices[pod['metadata']['name']].append(container['name'])

        return choices

    @accepts(Str('release_name'))
    async def pod_console_choices(self, release_name):
        """
        Returns choices for console access to a chart release.

        Output is a dictionary with names of pods as keys and containing names of containers which the pod
        comprises of.
        """
        return await self.retrieve_pod_with_containers(release_name)

    @accepts(Str('release_name'))
    async def pod_logs_choices(self, release_name):
        """
        Returns choices for accessing logs of any container in any pod in a chart release.
        """
        return await self.retrieve_pod_with_containers(release_name)

    @private
    async def validate_pod_log_args(self, release_name, pod_name, container_name):
        choices = await self.pod_logs_choices(release_name)
        if pod_name not in choices:
            raise CallError(f'Unable to locate {pod_name!r} pod.', errno=errno.ENOENT)
        elif container_name not in choices[pod_name]:
            raise CallError(
                f'Unable to locate {container_name!r} container in {pod_name!r} pod.', errno=errno.ENOENT
            )

    @accepts(
        Str('release_name'),
        Dict(
            'options',
            Int('limit_bytes', default=None, null=True, validators=[Range(min=1)]),
            Int('tail_lines', default=500, validators=[Range(min=1)], null=True),
            Str('pod_name', required=True, empty=False),
            Str('container_name', required=True, empty=False),
        )
    )
    @job(lock='chart_release_logs', pipes=['output'])
    def pod_logs(self, job, release_name, options):
        """
        Export logs of `options.container_name` container in `options.pod_name` pod in `release_name` chart release.

        `options.tail_lines` is an option to select how many lines of logs to retrieve for the said container. It
        defaults to 500. If set to `null`, it will retrieve complete logs of the container.

        `options.limit_bytes` is an option to select how many bytes to retrieve from the tail lines selected. If set
        to null ( which is the default ), it will not limit the bytes returned. To clarify, `options.tail_lines`
        is applied first and the required number of lines are retrieved and then `options.limit_bytes` is applied.

        Please refer to websocket documentation for downloading the file.
        """
        self.middleware.call_sync(
            'chart.release.validate_pod_log_args', release_name, options['pod_name'], options['container_name']
        )

        logs = self.middleware.call_sync(
            'k8s.pod.get_logs', options['pod_name'], options['container_name'], get_namespace(release_name),
            options['tail_lines'], options['limit_bytes']
        )
        job.pipes.output.w.write((logs or '').encode())

    @accepts()
    async def nic_choices(self):
        """
        Available choices for NIC which can be added to a pod in a chart release.
        """
        return await self.middleware.call('interface.choices')

    @accepts()
    async def used_ports(self):
        """
        Returns ports in use by applications.
        """
        return sorted(list(set({
            port['port']
            for chart_release in await self.middleware.call('chart.release.query')
            for port in chart_release['used_ports']
        })))

    @accepts()
    async def certificate_choices(self):
        """
        Returns certificates which can be used by applications.
        """
        return await self.middleware.call(
            'certificate.query', [['revoked', '=', False], ['cert_type_CSR', '=', False], ['parsed', '=', True]]
        )

    @accepts()
    async def certificate_authority_choices(self):
        """
        Returns certificate authorities which can be used by applications.
        """
        return await self.middleware.call(
            'certificateauthority.query', [['revoked', '=', False], ['parsed', '=', True]]
        )
