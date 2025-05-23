from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.directoryservices.ipa import generate_ipa_default_config
from middlewared.utils.directoryservices.constants import DSType


def render(service, middleware, render_ctx):
    ds = render_ctx['directoryservices.config']
    if ds['service_type'] != DSType.IPA.value:
        raise FileShouldNotExist()

    host = f'{ds["configuration"]["hostname"]}.{ds["configuration"]["domain"]}'.lower()
    return generate_ipa_default_config(
        host,
        ds['configuration']['basedn'],
        ds['configuration']['domain'].lower(),
        ds['kerberos_realm'],
        ds['configuration']['target_server']
    )
