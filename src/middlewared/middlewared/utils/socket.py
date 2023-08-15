import os
import socket


def is_socket_available(socket_path: str) -> bool:
    """Check if a Unix socket is available."""
    if not os.path.exists(socket_path):
        return False
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(socket_path)
        return True
    except socket.error:
        return False
    finally:
        s.close()
