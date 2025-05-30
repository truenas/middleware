from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.directoryservices.ipa import (
    generate_ipa_default_config, ipa_config_to_ipa_hostname
)
from middlewared.utils.directoryservices.constants import DSType


def render(service, middleware, render_ctx):
    ds = render_ctx['directoryservices.config']
    if ds['service_type'] != DSType.IPA.value:
        raise FileShouldNotExist()

    ipa_config = ds['configuration']
    return generate_ipa_default_config(
        ipa_config_to_ipa_hostname(ipa_config),
        ipa_config['basedn'],
        ipa_config['domain'].lower(),
        ipa_config['kerberos_realm'],
        ipa_config['target_server']
    )
