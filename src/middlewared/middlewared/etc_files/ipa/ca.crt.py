from middlewared.plugins.etc import FileShouldNotExist
from middlewared.plugins.directoryservices_.all import get_enabled_ds
from middlewared.utils.directoryservices.ipa_constants import IpaConfigName
from middlewared.utils.directoryservices.constants import DSType


def render(service, middleware):

    ds_obj = get_enabled_ds()
    if not ds_obj or ds_obj.name != DSType.IPA.value:
        raise FileShouldNotExist()

    cert = middleware.call_sync('certificateauthority.query', [
        'name', '=', IpaConfigName.IPA_CACERT.value
    ])

    if not cert:
        raise FileShouldNotExist()

    return cert[0]['certificate']
