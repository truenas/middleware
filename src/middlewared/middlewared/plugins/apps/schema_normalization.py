import os
from collections.abc import Callable

from middlewared.schema import Cron, Dict, Int, List, Str
from middlewared.service import Service

from .ix_apps.path import get_app_volume_path
from .schema_utils import get_list_item_from_value, RESERVED_NAMES


REF_MAPPING = {
    'definitions/certificate': 'certificate',
    'definitions/certificate_authority': 'certificate_authorities',
    'definitions/gpu_configuration': 'gpu_configuration',
    'normalize/acl': 'acl',
    'normalize/ix_volume': 'ix_volume',
}


class AppSchemaService(Service):

    class Config:
        namespace = 'app.schema'
        private = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for method in REF_MAPPING.values():
            assert isinstance(getattr(self, f'normalize_{method}'), Callable) is True

    async def normalize_and_validate_values(self, item_details, values, update, app_dir, app_data=None):
        dict_obj = await self.middleware.call(
            'app.schema.validate_values', item_details, values, update, app_data,
        )
        new_values, context = await self.normalize_values(dict_obj, values, update, {
            'app': {
                'name': app_dir.split('/')[-1],
                'path': app_dir,
            },
            'actions': [],
        })
        await self.perform_actions(context)
        return new_values

    async def perform_actions(self, context):
        for action in sorted(context['actions'], key=lambda d: 0 if d['method'] == 'update_volumes' else 1):
            await self.middleware.call(f'app.schema.action.{action["method"]}', *action['args'])

    async def normalize_values(self, dict_obj, values, update, context):
        for k in RESERVED_NAMES:
            # We reset reserved names from configuration as these are automatically going to
            # be added by middleware during the process of normalising the values
            values[k[0]] = k[1]()

        for attr in filter(lambda v: v.name in values, dict_obj.attrs.values()):
            values[attr.name] = await self.normalize_question(attr, values[attr.name], update, values, context)

        return values, context

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
                f'app.schema.normalize_{REF_MAPPING[ref]}', question_attr, value, complete_config, context
            )

        return value

    async def normalize_certificate(self, attr, value, complete_config, context):
        assert isinstance(attr, Int) is True

        if not value:
            return value

        complete_config['ix_certificates'][value] = await self.middleware.call('certificate.get_instance', value)

        return value

    async def normalize_certificate_authorities(self, attr, value, complete_config, context):
        assert isinstance(attr, Int) is True

        if not value:
            return value

        complete_config['ix_certificate_authorities'][value] = await self.middleware.call(
            'certificateauthority.get_instance', value
        )

        return value

    async def normalize_gpu_configuration(self, attr, value, complete_config, context):
        gpu_choices = {
            gpu['pci_slot']: gpu
            for gpu in await self.middleware.call('app.gpu_choices_internal') if not gpu['error']
        }
        if not gpu_choices:
            value['use_all_gpus'] = False

        for nvidia_gpu_pci_slot in list(value['nvidia_gpu_selection']):
            if nvidia_gpu_pci_slot not in gpu_choices or gpu_choices[nvidia_gpu_pci_slot]['vendor'] != 'NVIDIA':
                value['nvidia_gpu_selection'].pop(nvidia_gpu_pci_slot)

        return value

    async def normalize_ix_volume(self, attr, value, complete_config, context):
        # Let's allow ix volume attr to be a string as well making it easier to define a volume in questions.yaml
        assert isinstance(attr, (Dict, Str)) is True

        if isinstance(attr, Dict):
            vol_data = {'name': value['dataset_name'], 'properties': value.get('properties') or {}}
            acl_dict = value.get('acl_entries', {})
        else:
            vol_data = {'name': value, 'properties': {}}
            acl_dict = None

        ds_name = vol_data['name']

        action_dict = next((d for d in context['actions'] if d['method'] == 'update_volumes'), None)
        if not action_dict:
            context['actions'].append({
                'method': 'update_volumes',
                'args': [context['app']['name'], [vol_data]],
            })
        elif ds_name not in [v['name'] for v in action_dict['args'][-1]]:
            action_dict['args'][-1].append(vol_data)
        else:
            # We already have this in action dict, let's not add a duplicate
            return value

        host_path = os.path.join(get_app_volume_path(context['app']['name']), ds_name)
        complete_config['ix_volumes'][ds_name] = host_path

        if acl_dict:
            acl_dict['path'] = host_path
            await self.normalize_acl(Dict(), acl_dict, complete_config, context)
        return value

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
