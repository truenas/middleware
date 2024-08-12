import yaml

from middlewared.service import ValidationErrors


def validate_payload(data: dict, schema: str) -> dict:
    verrors = ValidationErrors()
    compose_keys = ('custom_compose_config', 'custom_compose_config_string')
    if all(not data.get(k) for k in compose_keys):
        verrors.add(f'{schema}.custom_compose_config', 'This field is required')
    elif all(data.get(k) for k in compose_keys):
        verrors.add(f'{schema}.custom_compose_config_string', 'Only one of these fields should be provided')

    compose_config = data.get('custom_compose_config')
    if data.get('custom_compose_config_string'):
        try:
            compose_config = yaml.safe_load(data['custom_compose_config_string'])
        except yaml.YAMLError:
            verrors.add('app_create.custom_compose_config_string', 'Invalid YAML provided')

    verrors.check()

    return compose_config
