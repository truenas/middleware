import os


HELM_SECRET_PREFIX = 'sh.helm.release'


def list_secrets(secrets_dir: str) -> dict[str, list[str]]:
    secrets = {
        'helm_secrets': [],
        'release_secrets': [],
    }
    with os.scandir(secrets_dir) as it:
        for entry in it:
            if not entry.is_file():
                continue

            if entry.name.startswith(HELM_SECRET_PREFIX):
                secrets['helm_secrets'].append(entry.name)
            else:
                secrets['release_secrets'].append(entry.name)

    secrets['helm_secrets'].sort()
    return secrets
