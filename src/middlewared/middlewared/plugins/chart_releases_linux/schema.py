import json

from collections import Callable

from middlewared.schema import Dict, List
from middlewared.service import private, Service, ValidationErrors

from .utils import get_network_attachment_definition_name


REF_MAPPING = {
    'normalise/interfaceConfiguration': 'interface_configuration'
}
RESERVED_NAMES = [
    ('externalInterfacesConfiguration', list),
    ('externalInterfacesConfigurationNames', list),
]


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for method in REF_MAPPING.values():
            assert isinstance(getattr(self, f'normalise_{method}'), Callable) is True

    @private
    async def get_normalised_values(self, attrs, values, update, context):
        # TODO: Add proper subquestions support ensuring it's supported at all relevant places
        for k in RESERVED_NAMES:
            # We reset reserved names from configuration as these are automatically going to
            # be added by middleware during the process of normalising the values
            values[k[0]] = k[1]()

        for attr in attrs:
            if not update and attr.name not in values and attr.default:
                values[attr.name] = attr.default
            if attr.name not in values:
                continue

            values[attr.name] = await self.normalise_question(attr, values[attr.name], update, values, context)

        return values

    @private
    async def normalise_question(self, question_attr, value, update, complete_config, context):
        if isinstance(question_attr, Dict):
            for attr in question_attr.attrs.values():
                if not update and attr.name not in value and attr.default:
                    value[attr.name] = attr.default
                if attr.name not in value:
                    continue

                value[attr.name] = await self.normalise_question(
                    attr, value[attr.name], update, complete_config, context
                )

        if isinstance(question_attr, List):
            for index, item in enumerate(value):
                for attr in question_attr.items:
                    try:
                        attr.validate(item)
                    except ValidationErrors:
                        pass
                    else:
                        value[index] = await self.normalise_question(attr, item, update, complete_config, context)
                        break

        for ref in filter(lambda k: k in REF_MAPPING, question_attr.ref):
            value = await self.middleware.call(
                f'chart.release.normalise_{REF_MAPPING[ref]}', question_attr, value, complete_config, context
            )

        return value

    @private
    async def normalise_interface_configuration(self, attr, value, complete_config, context):
        assert isinstance(attr, Dict) is True
        name = get_network_attachment_definition_name(
            context['release_name'], len(complete_config['externalInterfacesConfiguration'])
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
        iface_conf['ipam'] = ipam_config

        complete_config['externalInterfacesConfiguration'].append(json.dumps(iface_conf))
        complete_config['externalInterfacesConfigurationNames'].append(name)

        return value
