import copy
import json
import os

from collections import Callable

from middlewared.schema import Cron, Dict, List
from middlewared.service import private, Service

from .utils import get_list_item_from_value, get_network_attachment_definition_name, RESERVED_NAMES

# TODO: Let's please think of a better way to accomplish this as a whole

REF_MAPPING = {
    'normalize/interfaceConfiguration': 'interface_configuration',
    'normalize/ixVolume': 'ix_volume',
}


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for method in REF_MAPPING.values():
            assert isinstance(getattr(self, f'normalise_{method}'), Callable) is True

    @private
    async def get_normalised_values(self, dict_obj, values, update, context):
        for k in RESERVED_NAMES:
            # We reset reserved names from configuration as these are automatically going to
            # be added by middleware during the process of normalising the values
            values[k[0]] = k[1]()

        for attr in filter(lambda v: v.name in values, dict_obj.attrs.values()):
            values[attr.name] = await self.normalise_question(attr, values[attr.name], update, values, context)

        return values, context

    @private
    async def normalise_question(self, question_attr, value, update, complete_config, context):
        if value is None and isinstance(question_attr, (Dict, List)):
            # This shows that the value provided has been explicitly specified as null and if validation
            # was okay with it, we shouldn't try to normalise it
            return value

        if isinstance(question_attr, Dict) and not isinstance(question_attr, Cron):
            for attr in filter(lambda v: v.name in value, question_attr.attrs.values()):
                value[attr.name] = await self.normalise_question(
                    attr, value[attr.name], update, complete_config, context
                )

        if isinstance(question_attr, List):
            for index, item in enumerate(value):
                _, attr = get_list_item_from_value(item, question_attr)
                if attr:
                    value[index] = await self.normalise_question(attr, item, update, complete_config, context)

        for ref in filter(lambda k: k in REF_MAPPING, question_attr.ref):
            value = await self.middleware.call(
                f'chart.release.normalise_{REF_MAPPING[ref]}', question_attr, value, complete_config, context
            )

        return value

    @private
    async def normalise_interface_configuration(self, attr, value, complete_config, context):
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
    async def normalise_ix_volume(self, attr, value, complete_config, context):
        assert isinstance(attr, Dict) is True

        action_dict = next((d for d in context['actions'] if d['method'] == 'update_volumes_for_release'), None)
        if not action_dict:
            context['actions'].append({
                'method': 'update_volumes_for_release',
                'args': [copy.deepcopy(context['release']), [value['datasetName']]],
            })
        else:
            action_dict['args'][-1].append(value['datasetName'])

        complete_config['ixVolumes'].append({
            'hostPath': os.path.join(context['release']['path'], 'volumes/ix_volumes', value['datasetName']),
            'mountPath': value['mountPath'],
        })

        return value
