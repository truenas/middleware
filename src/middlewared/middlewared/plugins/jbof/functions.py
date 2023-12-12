import ipaddress


def jbof_static_ip(shelf_index, eth_index):
    return f'169.254.{20 + shelf_index}.{(eth_index <<2)+1}'


def initiator_static_ip(shelf_index, eth_index):
    return f'169.254.{20 + shelf_index}.{(eth_index <<2)+2}'


def static_ip_netmask_int():
    return 30


def static_ip_netmask_str(ip='169.254.20.0'):
    return str(ipaddress.IPv4Network(f'{ip}/{static_ip_netmask_int()}', strict=False).netmask)


def static_mtu():
    return 5000


def decode_static_ip(ip):
    """Decode a static IP.

    Returns a tuple of (shelf_index, eth_index) or None
    """
    try:
        ipaddress.ip_address(ip)
        if ip.startswith('169.254.'):
            vals = [int(x) for x in ip.split('.')]
            if vals[2] < 20:
                return
            shelf_index = vals[2] - 20
            eth_index = vals[3] >> 2
            return (shelf_index, eth_index)
    except ValueError:
        pass


def jbof_static_ip_from_initiator_ip(ip):
    result = decode_static_ip(ip)
    if result:
        return jbof_static_ip(*result)


def initiator_ip_from_jbof_static_ip(ip):
    result = decode_static_ip(ip)
    if result:
        return initiator_static_ip(*result)
