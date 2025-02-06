def parse_version_string(version_string: str) -> str | None:
    """
    This util retrieves version numbers from version string i.e 25.04.0 or 25.1.1.1.
    If an invalid version string is specified, it will return null in that case.

    It is being used for determining release notes url for docs team and in TNC service for heartbeat.
    """
    to_format = version_string.split('-')[0].split('.')  # looks like ['23', '10', '0', '1']
    if len(to_format) < 2:
        return None

    return '.'.join(to_format)
