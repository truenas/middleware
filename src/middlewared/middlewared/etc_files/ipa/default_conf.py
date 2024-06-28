from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.directoryservices.ipa import generate_ipa_default_config
from middlewared.utils.directoryservices.constants import DSType


def render(service, middleware, render_ctx):

    if render_ctx['directoryservices.status']['type'] != DSType.IPA.value:
        raise FileShouldNotExist()

    conf = middleware.call_sync('ldap.ipa_config')
    return generate_ipa_default_config(
        conf['host'],
        conf['basedn'],
        conf['domain'],
        conf['realm'],
        conf['target_server']
    )
