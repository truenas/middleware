from middlewared.plugins.etc import FileShouldNotExist
from middlewared.plugins.directoryservices_.all import get_enabled_ds
from middlewared.utils.directoryservices.ipa_constants import IpaConfigName
from middlewared.utils.directoryservices.constants import DSType


def render(service, middleware):

    ds_obj = get_enabled_ds()
    if not ds_obj or ds_obj.name != DSType.IPA.name:
        raise FileShouldNotExist()

    kt = middleware.call_sync('certificateauthority.query', [
        'name', '=', IpaConfigName.IPA_SMB_KEYTAB.value
    ])

    if not kt:
        raise FileShouldNotExist()

    return kt[0]['data']
