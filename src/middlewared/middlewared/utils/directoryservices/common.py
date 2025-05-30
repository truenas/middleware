from middlewared.utils.directoryservices.constants import DSType

def ds_config_to_fqdn(dict: ds_config) -> str:
    if ds_config['service_type'] not in (DSType.AD.value, DSType.IPA.value):
        raise ValueError(f'{ds_config["service_type"]}: service type unsupported.')

    return f'{ds_config["configuration"]["hostname"]}.{ds_config["configuration"]["domain"]}'.lower()
