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
    found_all_networks = ""  # If found, this will be 0.0.0.0/0 or ::/0 which we would like to exclude

    for v in networks:
        try:
            # Validity test and trap the old-school 'all-networks' entries: 0.0.0.0/0
            # Exclude these entries as they should be represented with no entry.
            if int(ip_network(v, strict=strict_test).network_address) == 0:
                found_all_networks = v
        except ValueError:
            not_valid.append(v)

    if not_valid:
        verrors.add(
            f"{schema_name}.networks",
            f"The following do not appear to be valid IPv4 or IPv6 networks: {', '.join(not_valid)}"
        )
    elif found_all_networks:
        verrors.add(
            f"{schema_name}.networks",
            f"Do not use {v} to represent all-networks.  "
            f"No entry is required to configure 'allow everybody'.  "
            f"Please remove {v}."
        )
    elif convert:
        # Perform the courtesy conversion to CIDR format
        return [str(ip_network(v, strict=False)) for v in networks]

    return networks


def sanitize_hosts(schema_name: str, hosts: list, verrors: ValidationErrors):
    """ host entries cannot contain spaces or quotes """
    regex = re.compile(r'.*[\s"]')
    not_valid = []
    found_all_hosts = ""
    for v in hosts:
        # Entries in hosts are pre-validated to be NonEmptyString
        if regex.match(v):
            not_valid.append(v)
        else:
            try:
                # Passed simple validity test, now trap the old-school 'all-hosts' entries: 0.0.0.0
                # Exclude these entries as they should be represented with no entry or '*'
                if int.from_bytes(ip_address(v).packed) == 0:
                    found_all_hosts = v
            except ValueError:
                # Not an IP address. Very likely path for a host entry
                pass

    if not_valid:
        verrors.add(
            f"{schema_name}.hosts",
            f"Cannot contain spaces or quotes: {', '.join(not_valid)}"
        )

    if found_all_hosts:
        verrors.add(
            f"{schema_name}.hosts",
            f"Do not use {v} to represent all-hosts.  "
            f"No entry is required to configure 'allow everybody'.  "
            f"Please remove {v} or replace with '*'."
        )


def validate_bind_ip(ips: list):
    """ Validate list strings are IP addresses """
    not_valid = []
    for ip in ips:
        # The join below does not play well with None
        if ip is None:
            ip = "None"
        try:
            ip_address(ip)
        except ValueError:
            not_valid.append(ip)
    if not_valid:
        raise ValueError(
            f"The following do not appear to be valid IPv4 or IPv6 addresses: {', '.join(not_valid)}"
        )
