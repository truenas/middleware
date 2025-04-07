from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.directoryservices.ipa_constants import IpaConfigName
from middlewared.utils.directoryservices.constants import DSType


def render(service, middleware, render_ctx):

    if render_ctx['directoryservices.config']['service_type'] != DSType.IPA.value:
        raise FileShouldNotExist()

    cert = middleware.call_sync('certificate.query', [[
        'name', '=', IpaConfigName.IPA_CACERT.value
    ]])

    if not cert:
        raise FileShouldNotExist()

    return cert[0]['certificate']
