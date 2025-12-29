import yaml

from middlewared.service import ValidationErrors

from .compose_utils import validate_compose_config
from .ix_apps.utils import safe_yaml_load


def validate_payload(data: dict, schema: str) -> dict:
    verrors = ValidationErrors()
    compose_keys = ('custom_compose_config', 'custom_compose_config_string')
    if all(not data.get(k) for k in compose_keys):
        verrors.add(f'{schema}.custom_compose_config', 'This field is required')
    elif all(data.get(k) for k in compose_keys):
        verrors.add(f'{schema}.custom_compose_config_string', 'Only one of these fields should be provided')

    compose_config = data.get('custom_compose_config')
    compose_yaml_string = None

    if data.get('custom_compose_config_string'):
        try:
            compose_config = safe_yaml_load(data['custom_compose_config_string'])
            compose_yaml_string = data['custom_compose_config_string']
        except yaml.YAMLError:
            verrors.add(f'{schema}.custom_compose_config_string', 'Invalid YAML provided')
    elif compose_config:
        compose_yaml_string = yaml.safe_dump(compose_config)

    # Validate the compose configuration with docker compose
    if compose_yaml_string and not verrors:
        is_valid, error_msg = validate_compose_config(compose_yaml_string)
        if not is_valid:
            field_name = (
                'custom_compose_config_string'
                if data.get('custom_compose_config_string')
                else 'custom_compose_config'
            )
            verrors.add(f'{schema}.{field_name}', f'Invalid compose configuration: {error_msg}')

    verrors.check()

    return compose_config
