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
            verrors.add(f'{schema}.custom_compose_config_string', 'Invalid YAML provided')
        else:
            if not isinstance(compose_config, dict):
                verrors.add(f'{schema}.custom_compose_config_string', 'YAML must represent a dictionary/object')
            elif 'services' not in compose_config or 'include' not in compose_config:
                verrors.add(f'{schema}.custom_compose_config_string', 'YAML is missing required \"services\" key or \"include\" key which points to a file that has services')

    verrors.check()

    return compose_config
