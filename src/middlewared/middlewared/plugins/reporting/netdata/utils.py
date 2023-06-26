import typing

from urllib.parse import urlencode


NETDATA_PORT = 22200  # FIXME: Change this to 6999
NETDATA_REQUEST_TIMEOUT = 30  # seconds
NETDATA_URI = f'http://127.0.0.1:{NETDATA_PORT}/api'


def get_query_parameters(query_params: typing.Optional[dict], prefix: str = '&') -> str:
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
