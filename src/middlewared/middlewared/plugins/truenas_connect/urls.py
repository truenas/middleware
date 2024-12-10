import urllib.parse


ACCOUNT_SERVICE_BASE_URL = 'https://account-service.dev.ixsystems.net/'
ACME_CONFIG_URL = urllib.parse.urljoin(ACCOUNT_SERVICE_BASE_URL, 'v1/accounts/{account_id}/acme')
BASE_URL = 'https://truenas.connect.dev.ixsystems.net/'
ACCOUNT_SERVICE_URL = urllib.parse.urljoin(ACCOUNT_SERVICE_BASE_URL, 'v1/accounts/{account_id}/systems/{system_id}')
HOSTNAME_URL = urllib.parse.urljoin(ACCOUNT_SERVICE_URL, 'hostnames/')
LECA_BASE_URL = 'https://leca-server.dev.ixsystems.net'
LECA_DNS_URL = urllib.parse.urljoin(LECA_BASE_URL, 'v1/dns-challenge')
LECA_HOSTNAME_URL = urllib.parse.urljoin(LECA_BASE_URL, 'v1/hostnames')
REGISTRATION_URI = urllib.parse.urljoin(BASE_URL, 'system/register')
REGISTRATION_FINALIZATION_URI = urllib.parse.urljoin(ACCOUNT_SERVICE_BASE_URL, 'v1/systems/finalize')
