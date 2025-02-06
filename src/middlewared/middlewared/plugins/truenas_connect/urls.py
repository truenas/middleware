import urllib.parse


def get_acme_config_url(tnc_config: dict) -> str:
    return urllib.parse.urljoin(tnc_config['account_service_base_url'], 'v1/accounts/{account_id}/acme')


def get_account_service_url(tnc_config: dict) -> str:
    return urllib.parse.urljoin(tnc_config['account_service_base_url'], 'v1/accounts/{account_id}/systems/{system_id}/')


def get_hostname_url(tnc_config: dict) -> str:
    return urllib.parse.urljoin(get_account_service_url(tnc_config), 'hostnames/')


def get_leca_dns_url(tnc_config: dict) -> str:
    return urllib.parse.urljoin(tnc_config['leca_service_base_url'], 'v1/dns-challenge')


def get_leca_cleanup_url(tnc_config: dict) -> str:
    return urllib.parse.urljoin(tnc_config['leca_service_base_url'], 'v1/hostnames')


def get_registration_uri(tnc_config: dict) -> str:
    return urllib.parse.urljoin(tnc_config['tnc_base_url'], f'system/register')


def get_registration_finalization_uri(tnc_config: dict) -> str:
    return urllib.parse.urljoin(tnc_config['account_service_base_url'], 'v1/systems/finalize')


def get_heartbeat_url(tnc_config: dict) -> str:
    return urllib.parse.urljoin(tnc_config['heartbeat_url'], 'v1/systems/{system_id}/{version}')
