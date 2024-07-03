import docker


PROJECT_KEY: str = 'com.docker.compose.project'


def get_docker_client() -> docker.DockerClient:
    return docker.from_env()
