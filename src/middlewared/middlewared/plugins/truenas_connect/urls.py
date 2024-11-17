import urllib.parse


BASE_URL = 'https://truenas.connect.dev.ixsystems.net/'
REGISTRATION_URI = urllib.parse.urljoin(BASE_URL, 'system/register')
REGISTRATION_FINALIZATION_URI = urllib.parse.urljoin(BASE_URL, 'v1/systems/finalize')
