from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.directoryservices.ipa import generate_ipa_default_config
from middlewared.utils.directoryservices.common import ds_config_to_fqdn
from middlewared.utils.directoryservices.constants import DSType


def render(service, middleware, render_ctx):
    ds = render_ctx['directoryservices.config']
    if ds['service_type'] != DSType.IPA.value:
        raise FileShouldNotExist()

    ipa_config = ds['configuration']
    return generate_ipa_default_config(
        ds_config_to_fqdn(ds).lower(),
        ipa_config['basedn'],
        ipa_config['domain'].lower(),
        ds['kerberos_realm'],
        ipa_config['target_server']
    )
