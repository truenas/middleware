import ipaddress

from middlewared.service_exception import ValidationErrors


def validate_address_pools(system_ips: list[dict], user_specified_networks: list[dict]):
    verrors = ValidationErrors()
    if not user_specified_networks:
        verrors.add('docker_update.address_pools', 'At least one address pool must be specified')
    verrors.check()

    network_cidrs = set([
        ipaddress.ip_network(f'{ip["address"]}/{ip["netmask"]}', False)
        for ip in system_ips
    ])
    seen_networks = set()
    for index, user_network in enumerate(user_specified_networks):
        if isinstance(user_network['base'], (ipaddress.IPv4Interface, ipaddress.IPv6Interface)):
            base_network = user_network['base'].network
            user_network['base'] = str(user_network['base'])
        else:
            base_network = ipaddress.ip_network(user_network['base'], False)

        # Validate subnet size vs. base network
        if base_network.prefixlen > user_network['size']:
            verrors.add(
                f'docker_update.address_pools.{index}.base',
                f'Base network {user_network["base"]} cannot be smaller than '
                f'the specified subnet size {user_network["size"]}'
            )

        # Validate no overlaps with system networks
        if any(base_network.overlaps(system_network) for system_network in network_cidrs):
            verrors.add(
                f'docker_update.address_pools.{index}.base',
                f'Base network {user_network["base"]} overlaps with an existing system network'
            )

        # Validate no duplicate networks
        if base_network in seen_networks:
            verrors.add(
                f'docker_update.address_pools.{index}.base',
                f'Base network {user_network["base"]} is a duplicate of another specified network'
            )

        seen_networks.add(base_network)

    verrors.check()
