import socket

import aiohttp


INTERNET_TIMEOUT = 15

CONNECTIVITY_CHECK_URL = 'http://www.gstatic.com/generate_204'
CONNECTIVITY_CHECK_TIMEOUT = 10

# Used by network.configuration
DEFAULT_NETWORK_DOMAIN = 'local'


async def check_internet_connectivity() -> str | None:
    """
    Check internet connectivity by making an HTTP request to a known endpoint.
    This verifies both DNS resolution and network connectivity.

    Returns:
        None if connectivity is successful, otherwise an error string indicating
        the type of failure:
        - DNS resolution error message if DNS lookup fails
        - Network connectivity error message if connection fails
        - Timeout error message if connection times out
    """
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=CONNECTIVITY_CHECK_TIMEOUT),
            trust_env=True
        ) as session:
            async with session.get(CONNECTIVITY_CHECK_URL) as resp:
                if resp.status == 204:
                    return None
                return f'Unexpected response from connectivity check: HTTP {resp.status}'
    except aiohttp.ClientConnectorError as e:
        if isinstance(e.os_error, socket.gaierror):
            return f'DNS resolution failed: {e.os_error.strerror}'
        return f'Network connectivity error: {e}'
    except aiohttp.ClientError as e:
        return f'Network connectivity error: {e}'
    except TimeoutError:
        return 'Network connectivity check timed out'
    except Exception as e:
        return f'Network connectivity check failed: {e}'
