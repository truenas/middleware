import base64


def generate_docker_auth_config(auth_list: list[dict[str, str]]) -> dict:
    auths = {}
    for auth in auth_list:
        auths[auth['uri']] = {
            # Encode username:password in base64
            'auth': base64.b64encode(f'{auth["username"]}:{auth["password"]}'.encode()).decode(),
        }

    return {
        'auths': auths,
    }
