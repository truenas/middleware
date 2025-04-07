from base64 import b64decode

from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.directoryservices.ipa_constants import IpaConfigName
from middlewared.utils.directoryservices.constants import DSType


def render(service, middleware, render_ctx):

    if render_ctx['directoryservices.config']['service_type'] != DSType.IPA.value:
        raise FileShouldNotExist()

    kt = middleware.call_sync('kerberos.keytab.query', [[
        'name', '=', IpaConfigName.IPA_SMB_KEYTAB.value
    ]])

    if not kt:
        raise FileShouldNotExist()

    return b64decode(kt[0]['file'])
