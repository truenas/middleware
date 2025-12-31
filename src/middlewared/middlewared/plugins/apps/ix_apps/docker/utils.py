import contextlib
import docker
import threading
from typing import Iterator


PROJECT_KEY: str = 'com.docker.compose.project'
DOCKER_SOCKET_URL = 'unix://var/run/docker.sock'

@contextlib.contextmanager
def get_docker_client() -> Iterator[docker.DockerClient]:
    """
    Context manager that yields a Docker client instance.
    The client is closed automatically when the context is exited.
    """
    client = docker.from_env(max_pool_size=20)
    client.api.trust_env = False
    try:
        yield client
    finally:
        client.close()


_STATS_CLIENT = None
_STATS_CLIENT_LOCK = threading.Lock()


def get_caching_docker_client() -> docker.DockerClient:
    """
    Returns a persistent Docker client instance that is reused across calls.
    """
    global _STATS_CLIENT
    if _STATS_CLIENT is None:
        with _STATS_CLIENT_LOCK:
            if _STATS_CLIENT is None:
                client = docker.DockerClient(
                    base_url=DOCKER_SOCKET_URL,
                    version='auto',
                    max_pool_size=20
                )
                client.api.trust_env = False 
                _STATS_CLIENT = client
    return _STATS_CLIENT