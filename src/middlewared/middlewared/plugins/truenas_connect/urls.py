import urllib.parse


BASE_URL = 'https://truenas.connect.dev.ixsystems.net/'
REGISTRATION_URI = urllib.parse.urljoin(BASE_URL, 'system/register')
REGISTRATION_FINALIZATION_URI = 'https://account-service.dev.ixsystems.net/v1/systems/finalize'
