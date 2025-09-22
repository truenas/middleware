import ipaddress
from pathlib import Path

from middlewared.utils.disks_.disk_class import RE_IS_PART


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


def get_sys_class_nvme():
    data = dict()
    for i in filter(lambda x: x.is_dir(), Path('/sys/class/nvme').iterdir()):
        data[i.name] = {
            'model': (i / 'model').read_text().strip(),
            'serial': (i / 'serial').read_text().strip(),
            'subsysnqn': (i / 'subsysnqn').read_text().strip(),
            'transport_address': (i / 'address').read_text().strip(),
            'transport_protocol': (i / 'transport').read_text().strip(),
            'state': (i / 'state').read_text().strip(),
        }
        if data[i.name]['transport_protocol'] == 'rdma':
            data[i.name]['hostnqn'] = (i / 'hostnqn').read_text().strip()
            data[i.name]['transport_address'] = data[i.name]['transport_address'].split('=')[1].split(',')[0].strip()

        namespaces, partitions = list(), list()
        for j in filter(lambda x: x.is_dir() and x.name.startswith(f'{i.name}n'), i.iterdir()):
            # nvme1n1/n2/n3 etc
            namespaces.append(j.name)
            for k in filter(lambda x: RE_IS_PART.search(x.name), j.iterdir()):
                # nvme1n1p1/p2/p3 etc
                partitions.append(k.name)

        data[i.name]['namespaces'] = namespaces
        data[i.name]['partitions'] = partitions

    return data
