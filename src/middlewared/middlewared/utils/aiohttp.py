import socket
import ssl

from aiohttp import ClientSession, ClientTimeout, TCPConnector
import certifi

from middlewared.utils.network import INTERNET_TIMEOUT


def client_session(**kwargs):
    return ClientSession(
        connector=TCPConnector(
            # When both A and AAAA records are present, but no usable IPv6 networking is configured,
            # `aiohttp` still tries to connect to IPv6 address and fails. Let's disable IPv6 for now.
            family=socket.AF_INET,
            # Use more up-to-date certificates from `certifi`
            ssl=ssl.create_default_context(cafile=certifi.where()),
        ),
        timeout=ClientTimeout(INTERNET_TIMEOUT),
        trust_env=True,
        **kwargs
    )
