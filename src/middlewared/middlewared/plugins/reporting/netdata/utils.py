from urllib.parse import urlencode

from middlewared.utils.disks_.disk_class import DiskEntry

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


def get_human_disk_name(disk: DiskEntry) -> str:
    """This will return a human-readable name which
    is used, primarily, in the title of the netdata
    for disk related reports."""
    # follows the form of <name> | <type> | <model> | <serial>
    # the _ONLY_ guaranteed value is the <name>
    # so we'll return "<attr>: Unknown" for any
    # attributes of the disk that we can't determine
    return ' | '.join(
        [
            disk.name,
            f'Type: {disk.media_type if disk.media_type else "Unknown"}',
            f'Model: {disk.model if disk.model else "Unknown"}',
            f'Serial: {disk.serial if disk.serial else "Unknown"}',
        ]
    )
