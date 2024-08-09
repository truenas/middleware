from apps_validation.portals import IX_NOTES_KEY, IX_PORTAL_KEY, validate_portals_and_notes, ValidationErrors

from .lifecycle import get_rendered_template_config_of_app


def normalized_port_value(scheme: str, port: int) -> str:
    return '' if ((scheme == 'http' and port == 80) or (scheme == 'https' and port == 443)) else f':{port}'


def get_portals_and_app_notes(app_name: str, version: str) -> dict:
    rendered_config = get_rendered_template_config_of_app(app_name, version)
    portal_and_notes_config = {
        k: rendered_config[k]
        for k in (IX_NOTES_KEY, IX_PORTAL_KEY)
        if k in rendered_config
    }
    config = {
        'portals': {},
        'notes': None,
    }
    if portal_and_notes_config:
        try:
            validate_portals_and_notes('portal', portal_and_notes_config)
        except ValidationErrors:
            return config

    portals = {}
    for portal in portal_and_notes_config.get(IX_PORTAL_KEY, []):
        port_value = normalized_port_value(portal['scheme'], portal['port'])
        portals[portal['name']] = f'{portal["scheme"]}://{portal["host"]}{port_value}{portal.get("path", "")}'

    return {
        'portals': portals,
        'notes': portal_and_notes_config.get(IX_NOTES_KEY),
    }
