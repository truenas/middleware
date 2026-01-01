import contextlib
import docker
import threading
from typing import Iterator


PROJECT_KEY: str = 'com.docker.compose.project'

_client = None
_client_lock = threading.Lock()


def _get_or_create_client() -> docker.DockerClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = docker.from_env()
            _client.api.trust_env = False
    return _client


@contextlib.contextmanager
def get_docker_client() -> Iterator[docker.DockerClient]:
    """
    Context manager that yields a global Docker client instance.
    If an exception occurs while using the client, it is closed and
    set to None so that a new client will be created on the next request.

    Yields:
        docker.DockerClient: The Docker client instance.
    """
    client = _get_or_create_client()
    try:
        yield client
    except Exception:
        with _client_lock:
            global _client
            if _client:
                try:
                    _client.close()
                except Exception:
                    pass
            _client = None
        raise
