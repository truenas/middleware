import ipaddress
import socket

import aiohttp


INTERNET_TIMEOUT = 15

CONNECTIVITY_CHECK_URL = 'http://www.gstatic.com/generate_204'
CONNECTIVITY_CHECK_TIMEOUT = 10


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
        # Some `aiohttp.ClientConnectorError` subclasses (i.e. `ClientConnectorCertificateError`) do not have `os_error`
        # attribute despite the parent class having one.
        if hasattr(e, 'os_error') and isinstance(e.os_error, socket.gaierror):
            return f'DNS resolution failed: {e.os_error.strerror}'
        return f'Network connectivity error: {e}'
    except aiohttp.ClientError as e:
        return f'Network connectivity error: {e}'
    except TimeoutError:
        return 'Network connectivity check timed out'
    except Exception as e:
        return f'Network connectivity check failed: {e}'


def system_ips_to_cidrs(system_ips: list[dict]) -> set:
    """Convert list of dicts from interface.ip_in_use to a set of ip_network objects."""
    return {
        ipaddress.ip_network(f'{ip["address"]}/{ip["netmask"]}', strict=False)
        for ip in system_ips
    }


def validate_network_overlaps(schema: str, network, system_cidrs: set, verrors) -> None:
    """Add a validation error if `network` overlaps any CIDR in `system_cidrs`.

    Only compares networks of the same address family to avoid TypeError.
    """
    if any(
        network.overlaps(cidr) for cidr in system_cidrs
        if network.version == cidr.version
    ):
        verrors.add(schema, f'Network {network} overlaps with an existing system network')
