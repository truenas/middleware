import re

from ipaddress import ip_address, ip_network
from middlewared.service import ValidationErrors


def confirm_unique(schema_name: str, item_name: str, data: dict, verrors: ValidationErrors):
    """ Generat validation errors if list includes non-unique items """
    s = set()
    not_unique = []
    for v in data[item_name]:
        if v in s:
            not_unique.append(v)
        s.add(v)

    if not_unique:
        verrors.add(
            f"{schema_name}.{item_name}",
            f"Entries must be unique, the following are not: {', '.join(not_unique)}"
        )


def sanitize_networks(
    schema_name: str, networks: list, verrors: ValidationErrors, strict_test=True, convert=False
) -> list[str] | None:
    """ Entries must be acceptible to ip_network and make all valid entries CIDR formatted """
    not_valid = []
    for v in networks:
        try:
            ip_network(v, strict=strict_test)
        except ValueError:
            not_valid.append(v)

    if not_valid:
        verrors.add(
            f"{schema_name}.networks",
            f"The following do not appear to be valid IPv4 or IPv6 networks: {', '.join(not_valid)}"
        )
    elif convert:
        # Perform the courtesy conversion to CIDR format
        return [str(ip_network(v, strict=False)) for v in networks]


def sanitize_hosts(schema_name: str, hosts: list, verrors: ValidationErrors):
    """ host entries cannot contain spaces or quotes """
    regex = re.compile(r'.*[\s"]')
    not_valid = []
    for v in hosts:
        # Entries in hosts are pre-validated to be NonEmptyString
        if regex.match(v):
            not_valid.append(v)

    if not_valid:
        verrors.add(
            f"{schema_name}.hosts",
            f"Cannot contain spaces or quotes: {', '.join(not_valid)}"
        )


def validate_bind_ip(ips: list):
    """ Validate list strings are IP addresses """
    not_valid = []
    for ip in ips:
        # The join below does no play well with None
        if ip is None:
            ip == "None"
        try:
            ip_address(ip)
        except ValueError:
            not_valid.append(ip)
    if not_valid:
        raise ValueError(
            f"The following do not appear to be valid IPv4 or IPv6 addresses: {', '.join(not_valid)}"
        )
