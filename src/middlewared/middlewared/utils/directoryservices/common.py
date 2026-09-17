from middlewared.utils.directoryservices.constants import DSType


def ds_hostname_is_fqdn(ds_config: dict) -> bool:
    """ Whether the configured hostname is already a fully-qualified domain name.

    IPA permits the TrueNAS host account to live in a DNS zone other than the IPA domain
    (a subdomain of it, or an unrelated zone entirely), so the IPA hostname may be given
    as a complete FQDN. A dot in the name is what distinguishes the two forms: a bare
    hostname such as "truenasnyc" never contains one.
    """
    if ds_config['service_type'] != DSType.IPA.value:
        return False

    return '.' in ds_config['configuration']['hostname']


def ds_config_to_fqdn(ds_config: dict) -> str:
    if ds_config['service_type'] not in (DSType.AD.value, DSType.IPA.value):
        raise ValueError(f'{ds_config["service_type"]}: service type unsupported.')

    # WARNING: nsupdate with GSSAPI may expect the domain component to be upper case so
    # any case normalization should be handled by consumer.
    if ds_hostname_is_fqdn(ds_config):
        return ds_config['configuration']['hostname']

    return f'{ds_config["configuration"]["hostname"]}.{ds_config["configuration"]["domain"]}'
