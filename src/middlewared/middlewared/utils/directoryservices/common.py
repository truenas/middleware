from middlewared.utils.directoryservices.constants import DSType


def ds_config_to_fqdn(ds_config: dict) -> str:
    if ds_config['service_type'] not in (DSType.AD.value, DSType.IPA.value):
        raise ValueError(f'{ds_config["service_type"]}: service type unsupported.')

    # WARNING: nsupdate with GSSAPI may expect the domain component to be upper case so
    # any case normalization should be handled by consumer.
    return f'{ds_config["configuration"]["hostname"]}.{ds_config["configuration"]["domain"]}'
