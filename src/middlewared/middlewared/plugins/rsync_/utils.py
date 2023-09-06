def get_host_key_file_contents_from_ssh_credentials(credentials: dict) -> str:
    return '\n'.join([
        (
            f'{credentials["host"]} {host_key}' if credentials['port'] == 22
            else f'[{credentials["host"]}]:{credentials["port"]} {host_key}'
        )
        for host_key in credentials['remote_host_key'].split('\n')
        if host_key.strip() and not host_key.strip().startswith('#')
    ])
