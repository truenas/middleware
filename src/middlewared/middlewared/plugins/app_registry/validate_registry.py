from docker.errors import APIError, DockerException

from middlewared.plugins.apps.ix_apps.docker.utils import get_docker_client


def validate_registry_credentials(registry: str, username: str, password: str) -> bool:
    """
    Validates Docker registry credentials using the Docker SDK.

    Args:
        registry (str): The URL of the Docker registry (e.g., "registry1.example.com").
        username (str): The username for the registry.
        password (str): The password for the registry.

    Returns:
        bool: True if the credentials are valid, False otherwise.
    """
    with get_docker_client() as client:
        try:
            client.login(username=username, password=password, registry=registry)
        except (APIError, DockerException):
            return False
        else:
            return True

    return False
