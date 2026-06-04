import base64

from middlewared.utils.docker_registry import DEFAULT_DOCKER_REGISTRY, normalize_registry_authority

# Docker CLI canonicalizes any Docker Hub login to this exact key in config.json and
# only ever looks under this key when pulling a docker.io image — regardless of which
# Hub hostname (docker.io / registry-1.docker.io / index.docker.io) the user typed.
# Storing creds under any other key for a Hub registry produces a working-looking
# config.json that docker silently ignores at pull time.
DOCKER_HUB_CANONICAL_URI = 'https://index.docker.io/v1/'


def _docker_cli_auth_key(uri: str) -> str:
    """Map a stored registry URI to the auths-map key docker CLI will look under.

    Pass-through for everything except Docker Hub aliases, which all collapse to
    ``DOCKER_HUB_CANONICAL_URI`` so ``docker compose pull`` of a docker.io image
    finds the credentials no matter which Hub URI the user entered in the UI.
    """
    if normalize_registry_authority(uri) == DEFAULT_DOCKER_REGISTRY:
        return DOCKER_HUB_CANONICAL_URI
    return uri


def generate_docker_auth_config(auth_list: list[dict[str, str]]) -> dict:
    auths = {}
    for auth in auth_list:
        # Key by what docker CLI will look up, not by the raw stored URI — see
        # _docker_cli_auth_key for the Docker Hub quirk this guards against.
        auths[_docker_cli_auth_key(auth['uri'])] = {
            # Encode username:password in base64
            'auth': base64.b64encode(f'{auth["username"]}:{auth["password"]}'.encode()).decode(),
        }

    return {
        'auths': auths,
    }
