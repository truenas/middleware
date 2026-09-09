import shlex


def get_host_key_file_contents_from_ssh_credentials(credentials: dict) -> str:
    return '\n'.join([
        (
            f'{credentials["host"]} {host_key}' if credentials['port'] == 22
            else f'[{credentials["host"]}]:{credentials["port"]} {host_key}'
        )
        for host_key in credentials['remote_host_key'].split('\n')
        if host_key.strip() and not host_key.strip().startswith('#')
    ])


def quote_extra_args(extra: list[str]) -> list[str]:
    args = []
    for arg in extra:
        try:
            args.extend(shlex.split(arg))
        except ValueError:
            args.append(arg)

    return [shlex.quote(arg) for arg in args]
