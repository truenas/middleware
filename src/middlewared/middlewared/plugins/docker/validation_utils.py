import ipaddress

from middlewared.schema import ValidationErrors


def validate_address_pools(system_ips: list[dict], user_specified_networks: list[dict]):
    verrors = ValidationErrors()
    network_cidrs = set([
        ipaddress.ip_network(f'{ip["address"]}/{ip["netmask"]}', False)
        for ip in system_ips
    ])
    seen_networks = set()
    for index, user_network in enumerate(user_specified_networks):
        base_network = ipaddress.ip_network(user_network['base'], False)
        subnet_prefix = int(user_network['base'].split('/')[-1])

        # Validate subnet size vs. base network
        if subnet_prefix > user_network['size']:
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
