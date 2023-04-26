import copy
import json
import os
try:
    from collections.abc import Callable
except ImportError:
    from collections import Callable

from middlewared.schema import Cron, Dict, Int, List, Str
from middlewared.service import private, Service
from .schema import get_list_item_from_value
from .utils import CONTEXT_KEY_NAME, get_network_attachment_definition_name, RESERVED_NAMES

REF_MAPPING = {
    'definitions/certificate': 'certificate',
    'definitions/certificateAuthority': 'certificate_authorities',
    'definitions/gpuConfiguration': 'gpu_configuration',
    'normalize/interfaceConfiguration': 'interface_configuration',
    'normalize/acl': 'acl',
    'normalize/ixVolume': 'ix_volume',
}


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for method in REF_MAPPING.values():
            assert isinstance(getattr(self, f'normalize_{method}'), Callable) is True

    @private
    async def get_normalized_values(self, dict_obj, values, update, context):
        for k in RESERVED_NAMES:
            # We reset reserved names from configuration as these are automatically going to
            # be added by middleware during the process of normalising the values
            values[k[0]] = k[1]()

        for attr in filter(lambda v: v.name in values, dict_obj.attrs.values()):
            values[attr.name] = await self.normalize_question(attr, values[attr.name], update, values, context)

        return values, context

    @private
    async def normalize_question(self, question_attr, value, update, complete_config, context):
        if value is None and isinstance(question_attr, (Dict, List)):
            # This shows that the value provided has been explicitly specified as null and if validation
            # was okay with it, we shouldn't try to normalize it
            return value

        if isinstance(question_attr, Dict) and not isinstance(question_attr, Cron):
            for attr in filter(lambda v: v.name in value, question_attr.attrs.values()):
                value[attr.name] = await self.normalize_question(
                    attr, value[attr.name], update, complete_config, context
                )

        if isinstance(question_attr, List):
            for index, item in enumerate(value):
                _, attr = get_list_item_from_value(item, question_attr)
                if attr:
                    value[index] = await self.normalize_question(attr, item, update, complete_config, context)

        for ref in filter(lambda k: k in REF_MAPPING, question_attr.ref):
            value = await self.middleware.call(
                f'chart.release.normalize_{REF_MAPPING[ref]}', question_attr, value, complete_config, context
            )

        return value

    @private
    async def normalize_gpu_configuration(self, attr, value, complete_config, context):
        assert isinstance(attr, Dict) is True
        nvidia_attr = {'addNvidiaRuntimeClass': bool(value.get('nvidia.com/gpu'))}
        try:
            complete_config[CONTEXT_KEY_NAME].update(nvidia_attr)
        except KeyError:
            complete_config[CONTEXT_KEY_NAME] = nvidia_attr
        return value

    @private
    async def normalize_interface_configuration(self, attr, value, complete_config, context):
        assert isinstance(attr, Dict) is True
        name = get_network_attachment_definition_name(
            context['release']['name'], len(complete_config['ixExternalInterfacesConfiguration'])
        )
        host_iface = value['hostInterface']
        iface_conf = {
            'cniVersion': '0.3.1',
            'name': name,
        }
        if host_iface.startswith('br'):
            iface_conf.update({
                'type': 'bridge',
                'bridge': host_iface,
            })
        else:
            iface_conf.update({
                'type': 'macvlan',
                'master': host_iface,
            })

        ipam = value['ipam']
        ipam_config = {}
        if ipam['type'] == 'dhcp':
            ipam_config['type'] = 'dhcp'
        else:
            ipam_config.update({
                'type': 'static',
                'addresses': [{'address': i} for i in ipam['staticIPConfigurations']],
                'routes': [{'dst': d['destination'], 'gw': d['gateway']} for d in ipam['staticRoutes']]
            })

        iface_conf['ipam'] = ipam_config

        complete_config['ixExternalInterfacesConfiguration'].append(json.dumps(iface_conf))
        complete_config['ixExternalInterfacesConfigurationNames'].append(name)

        return value

    @private
    async def normalize_ix_volume(self, attr, value, complete_config, context):
        # Let's allow ix volume attr to be a string as well making it easier to define a volume in questions.yaml
        assert isinstance(attr, (Dict, Str)) is True

        if isinstance(attr, Dict):
            vol_data = {'name': value['datasetName'], 'properties': value.get('properties') or {}}
            acl_dict = value.get('aclEntries', {})
        else:
            vol_data = {'name': value, 'properties': {}}
            acl_dict = None
        ds_name = vol_data['name']

        action_dict = next((d for d in context['actions'] if d['method'] == 'update_volumes_for_release'), None)
        if not action_dict:
            context['actions'].append({
                'method': 'update_volumes_for_release',
                'args': [copy.deepcopy(context['release']), [vol_data]],
            })
        elif ds_name not in [v['name'] for v in action_dict['args'][-1]]:
            action_dict['args'][-1].append(vol_data)
        else:
            # We already have this in action dict, let's not add a duplicate
            return value
        host_path = os.path.join(context['release']['path'], 'volumes/ix_volumes', ds_name)
        complete_config['ixVolumes'].append({
            'hostPath': host_path,
        })

        if acl_dict:
            acl_dict['path'] = host_path
            await self.normalize_acl(Dict(), acl_dict, complete_config, context)
        return value

    @private
    async def normalize_certificate(self, attr, value, complete_config, context):
        assert isinstance(attr, Int) is True

        if not value:
            return value

        complete_config['ixCertificates'][value] = await self.middleware.call('certificate.get_instance', value)

        return value

    @private
    async def normalize_certificate_authorities(self, attr, value, complete_config, context):
        assert isinstance(attr, Int) is True

        if not value:
            return value

        complete_config['ixCertificateAuthorities'][value] = await self.middleware.call(
            'certificateauthority.get_instance', value
        )

        return value

    @private
    async def normalize_acl(self, attr, value, complete_config, context):
        assert isinstance(attr, Dict) is True

        if not value or any(not value[k] for k in ('entries', 'path')):
            return value

        if (action_dict := next((d for d in context['actions'] if d['method'] == 'apply_acls'), None)) is None:
            context['actions'].append({
                'method': 'apply_acls',
                'args': [{value['path']: value}],
            })
        elif value['path'] not in action_dict['args'][-1]:
            action_dict['args'][-1][value['path']] = value
        else:
            # We already have this in action dict, let's not add a duplicate
            return value

        return value
