import contextlib
import docker


PROJECT_KEY: str = 'com.docker.compose.project'


@contextlib.contextmanager
def get_docker_client() -> docker.DockerClient:
    client = docker.from_env()
    try:
        yield client
    finally:
        client.close()
