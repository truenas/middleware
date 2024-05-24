from middlewared.plugins.etc import FileShouldNotExist
from middlewared.plugins.directoryservices_.all import get_enabled_ds
from middlewared.utils.directoryservices.ipa import generate_ipa_default_config
from middlewared.utils.directoryservices.constants import DSType


def render(service, middleware):

    ds_obj = get_enabled_ds()
    if not ds_obj or ds_obj.name != DSType.IPA.value:
        raise FileShouldNotExist()

    conf = ds_obj.setup_legacy()
    return generate_ipa_default_config(
        conf['host'],
        conf['domain'],
        conf['realm'],
        conf['target_server']
    )
