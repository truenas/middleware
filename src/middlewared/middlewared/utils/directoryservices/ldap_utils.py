from urllib.parse import urlparse


def hostnames_to_uris(hostname_list: list, use_ldaps: bool) -> list:
    scheme = 'ldaps' if use_ldaps else 'ldap'
    out = []

    for host in set(hostname_list):
        parsed = urlparse(f'{scheme}://{host}')
        try:
            port = parsed.port
            host = parsed.hostname
        except ValueError:
            port = None

        if port is None:
            port = 636 if use_ldaps else 389

        out.append(f'{scheme}://{host}:{port}')

    return out
