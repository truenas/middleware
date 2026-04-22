import contextlib
from collections.abc import Iterator

import docker


PROJECT_KEY: str = 'com.docker.compose.project'


@contextlib.contextmanager
def get_docker_client() -> Iterator[docker.DockerClient]:
    client = docker.from_env()
    try:
        yield client
    finally:
        client.close()  # type: ignore[no-untyped-call]
