import struct
from socket import AF_INET, AF_UNIX
from unittest.mock import MagicMock, patch

from middlewared.utils import MIDDLEWARE_NGINX_SOCK
from middlewared.utils.origin import ConnectionOrigin, get_tcp_ip_info


def _request_for(sock):
    request = MagicMock()
    request.transport.get_extra_info.return_value = sock
    return request


def test_nginx_unix_socket_classified_as_tcp_origin():
    """Connections arriving on the private nginx unix socket must be classified
    as TCP/IP origins built from the reverse-proxy headers (not as unix-socket
    peer-credential origins), so that the UI allowlist is enforced and they are
    never auto-authenticated as the local/root peer."""
    sock = MagicMock()
    sock.family = AF_UNIX
    sock.getsockname.return_value = MIDDLEWARE_NGINX_SOCK
    request = _request_for(sock)

    tcp_origin = ConnectionOrigin(family=AF_INET, rem_addr="1.2.3.4", rem_port=5678)
    with patch(
        "middlewared.utils.origin.get_tcp_ip_info", return_value=tcp_origin
    ) as gti:
        origin = ConnectionOrigin.create(request)

    gti.assert_called_once_with(sock, request)
    assert origin is tcp_origin
    assert origin.is_tcp_ip_family is True
    assert origin.is_unix_family is False
    # Peer credentials must not be consulted for the nginx socket.
    sock.getsockopt.assert_not_called()


def test_local_unix_socket_uses_peer_credentials():
    """A connection on any other unix socket (e.g. midclt's middlewared.sock)
    keeps the existing unix-credential behavior."""
    sock = MagicMock()
    sock.family = AF_UNIX
    sock.getsockname.return_value = "/run/middleware/middlewared.sock"
    sock.getsockopt.return_value = struct.pack("3i", 4321, 1000, 1000)
    request = _request_for(sock)

    with (
        patch("middlewared.utils.origin.get_login_uid", return_value=1000),
        patch("middlewared.utils.origin.get_tcp_ip_info") as gti,
    ):
        origin = ConnectionOrigin.create(request)

    gti.assert_not_called()
    assert origin.is_unix_family is True
    assert origin.pid == 4321
    assert origin.uid == 1000
    assert origin.gid == 1000


def test_get_tcp_ip_info_rejects_headerless_non_ip_socket():
    """Without the X-Real-Remote-* headers we cannot determine an origin for a
    non-TCP/IP socket (such as the nginx unix socket reached unexpectedly); it
    must return None rather than attempt to unpack a unix peer name."""
    sock = MagicMock()
    sock.family = AF_UNIX
    request = MagicMock()
    request.headers = {}

    assert get_tcp_ip_info(sock, request) is None
    sock.getpeername.assert_not_called()
