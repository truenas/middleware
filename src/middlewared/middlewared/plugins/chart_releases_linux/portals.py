import base64
import os
import yaml

from middlewared.service import private, Service
from middlewared.utils import get


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    def retrieve_portals_for_chart_release(self, release_data, node_ip=None):
        questions_yaml_path = os.path.join(
            release_data['path'], 'charts', release_data['chart_metadata']['version'], 'questions.yaml'
        )
        if not os.path.exists(questions_yaml_path):
            return {}

        with open(questions_yaml_path, 'r') as f:
            portals = yaml.safe_load(f.read()).get('portals') or {}

        if not portals:
            return portals

        if not node_ip:
            node_ip = self.middleware.call_sync('kubernetes.node_ip')

        def tag_func(key):
            return self.parse_tag(release_data, key, node_ip)

        cleaned_portals = {}
        for portal_type, schema in portals.items():
            t_portals = []
            path = schema.get('path') or '/'
            for protocol in filter(bool, map(tag_func, schema['protocols'])):
                for host in filter(bool, map(tag_func, schema['host'])):
                    for port in filter(bool, map(tag_func, schema['ports'])):
                        t_portals.append(f'{protocol}://{host}:{port}{path}')

            cleaned_portals[portal_type] = t_portals

        return cleaned_portals

    @private
    def parse_tag(self, release_data, tag, node_ip):
        tag = self.parse_k8s_resource_tag(release_data, tag)
        if not tag:
            return
        if tag == '$node_ip':
            return node_ip
        elif tag.startswith('$variable-'):
            return get(release_data['config'], tag[len('$variable-'):])

        return tag

    @private
    def parse_k8s_resource_tag(self, release_data, tag):
        # Format expected here is "$kubernetes-resource_RESOURCE-TYPE_RESOURCE-NAME_KEY-NAME"
        if not tag.startswith('$kubernetes-resource'):
            return tag

        if tag.count('_') < 3:
            return

        _, resource_type, resource_name, key = tag.split('_', 3)
        if resource_type not in ('configmap', 'secret'):
            return

        resource = self.middleware.call_sync(
            f'k8s.{resource_type}.query', [
                ['metadata.namespace', '=', release_data['namespace']], ['metadata.name', '=', resource_name]
            ]
        )
        if not resource or 'data' not in resource[0] or not isinstance(resource[0]['data'].get(key), (int, str)):
            # Chart creator did not create the resource or we have a malformed
            # secret/configmap, nothing we can do on this end
            return
        else:
            value = resource[0]['data'][key]

        if resource_type == 'secret':
            value = base64.b64decode(value)

        return str(value)
