import base64
import os
import threading
import yaml

from middlewared.service import private, Service
from middlewared.utils import get


PORTAL_LOCK = threading.Lock()


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    PORTAL_CACHE = {}

    @private
    def clear_portal_cache(self):
        with PORTAL_LOCK:
            self.PORTAL_CACHE = {}

    @private
    def get_portal_cache(self):
        return self.PORTAL_CACHE

    @private
    def clear_chart_release_portal_cache(self, release_name):
        with PORTAL_LOCK:
            self.PORTAL_CACHE.pop(release_name, None)

    @private
    def retrieve_portals_for_chart_release(self, release_data, node_ip):
        with PORTAL_LOCK:
            if release_data['name'] not in self.PORTAL_CACHE:
                self.PORTAL_CACHE[release_data['name']] = self.retrieve_portals_for_chart_release_impl(
                    release_data, node_ip
                )
            return self.PORTAL_CACHE[release_data['name']]

    @private
    def retrieve_portals_for_chart_release_impl(self, release_data, node_ip):
        questions_yaml_path = os.path.join(
            release_data['path'], 'charts', release_data['chart_metadata']['version'], 'questions.yaml'
        )
        if not os.path.exists(questions_yaml_path):
            return {}

        # If portals are defined in values.yaml/questions.yaml parse them
        if len(release_data['config'].get('iXPortals')):
            portals = release_data['config'].get('iXPortals')
            return self.get_ixportals(portals, node_ip)

        # TODO: remove some time after a release with NAS-119932 (limit app ver to os var) included
        if release_data['chart_metadata']['name'] == 'ix-chart':
            return self.get_ix_chart_portal(release_data, node_ip)

        with open(questions_yaml_path, 'r') as f:
            portals = yaml.safe_load(f.read()).get('portals') or {}

        if not portals:
            return portals

        def tag_func(key):
            return self.parse_tag(release_data, key, node_ip)

        cleaned_portals = {}
        for portal_type, schema in portals.items():
            t_portals = []
            path = tag_func(schema.get('path') or '/')
            for protocol in filter(bool, map(tag_func, schema['protocols'])):
                for host in filter(bool, map(tag_func, schema['host'])):
                    for port in filter(bool, map(tag_func, schema['ports'])):
                        t_portals.append(f'{protocol}://{host}:{port}{path}')

            cleaned_portals[portal_type] = t_portals

        return cleaned_portals

    # TODO: remove some time after a release with NAS-119932 (limit app ver to os var) included
    @private
    def get_ix_chart_portal(self, release_data, node_ip):
        portal_config = release_data['config'].get('portalDetails')
        if not portal_config or not release_data['config'].get('enableUIPortal'):
            return {}
        host = node_ip if portal_config['useNodeIP'] else portal_config['host']
        return {
            portal_config['portalName']: [f'{portal_config["protocol"]}://{host}:{portal_config["port"]}']
        }

    # Reads a "ixPortals" dict in values.yaml, after parsing questions.yaml
    # Creates portal references for each portal in the list
    # This also allows for moving some/future logic changes to the charts repo
    @private
    def get_ixportals(self, portals, node_ip):
        stored_portals = {}
        for name, portal_config in portals.items():
            if not portal_config.get('enabled'):
                return {}
            host = portal_config['host'] if portal_config['host'] else node_ip
            protocol = 'http' if not portal_config['protocol'] else portal_config['protocol']
            path = '' if not portal_config.get['path'] else f'/{portal_config["path"]}'
            port = portal_config.get['port']
            if (port == 80 and protocol == 'http') or (port == 443 and protocol == 'https') or (not port):
                port = ''
            else:
                port = f':{port}'
            stored_portals[name] = [f'{protocol}://{host}{port}/{path}']

        return stored_portals

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
