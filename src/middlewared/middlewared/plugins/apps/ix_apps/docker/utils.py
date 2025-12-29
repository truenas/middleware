import contextlib
import docker
from typing import Iterator


PROJECT_KEY: str = 'com.docker.compose.project'


@contextlib.contextmanager
def get_docker_client() -> Iterator[docker.DockerClient]:
    client = docker.from_env(max_pool_size=20)
    client.api.trust_env = False
    try:
        yield client
    finally:
        client.close()
