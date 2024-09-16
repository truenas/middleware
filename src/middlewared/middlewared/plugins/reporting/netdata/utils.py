from urllib.parse import urlencode


NETDATA_PORT = 6999
NETDATA_REQUEST_TIMEOUT = 30  # seconds
NETDATA_URI = f'http://127.0.0.1:{NETDATA_PORT}/api'
NETDATA_UPDATE_EVERY = 2  # seconds


def get_query_parameters(query_params: dict | None, prefix: str = '&') -> str:
    """
    retrieve complete uri by adding query params to the uri by properly normalizing
    each query param and their special characters
    """
    if query_params is None:
        return ''

    # Normalize query parameters
    normalized_params = {key: str(value) for key, value in query_params.items()}
    # Encode and append query parameters to the base URI
    encoded_params = urlencode(normalized_params)
    return f'{prefix}{encoded_params}'


def get_human_disk_name(disk_details: dict) -> str:
    """
    This will return a human-readable name for the disk which is guaranteed to be unique
    """
    identifier = disk_details['identifier']
    disk_type = disk_details['type']
    if disk_type == 'SSD' and disk_details['name'].startswith('nvme'):
        disk_type = 'NVME'

    model = disk_details['model']

    human_identifier = ''
    if disk_type:
        human_identifier = f'{disk_type} | '

    if model:
        human_identifier += f'{model} Model | '

    human_identifier += f'{identifier}'

    return human_identifier
