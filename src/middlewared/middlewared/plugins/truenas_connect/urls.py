import urllib.parse


ACCOUNT_SERVICE_BASE_URL = 'https://account-service.dev.ixsystems.net/'
BASE_URL = 'https://truenas.connect.dev.ixsystems.net/'
ACCOUNT_SERVICE_URL = urllib.parse.urljoin(ACCOUNT_SERVICE_BASE_URL, 'v1/accounts/{account_id}/systems/{system_id}/')
HOSTNAME_URL = urllib.parse.urljoin(ACCOUNT_SERVICE_URL, 'hostnames/')
LECA_DNS_URL = 'https://leca-server.dev.ixsystems.net/v1/dns-challenge'
LECA_CLEANUP_URL = 'https://leca-server.dev.ixsystems.net/v1/hostnames'
REGISTRATION_URI = urllib.parse.urljoin(BASE_URL, 'system/register')
REGISTRATION_FINALIZATION_URI = urllib.parse.urljoin(ACCOUNT_SERVICE_BASE_URL, 'v1/systems/finalize')


def get_acme_config_url(tnc_config: dict) -> str:
    return urllib.parse.urljoin(tnc_config['account_service_base_url'], 'v1/accounts/{account_id}/acme')
