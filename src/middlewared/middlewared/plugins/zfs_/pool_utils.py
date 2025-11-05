import libzfs

from collections import defaultdict


SEARCH_PATHS = ['/dev/disk/by-partuuid', '/dev']


def convert_topology(zfs, vdevs):
    topology = defaultdict(list)
    for vdev in vdevs:
        children = []
        for device in vdev['devices']:
            z_cvdev = libzfs.ZFSVdev(zfs, 'disk')
            z_cvdev.type = 'disk'
            z_cvdev.path = device
            children.append(z_cvdev)

        if vdev['type'] == 'STRIPE':
            topology[vdev['root'].lower()].extend(children)
        else:
            z_vdev = libzfs.ZFSVdev(zfs, 'disk')
            z_vdev.children = children
            if vdev['type'].startswith('DRAID'):
                z_vdev.type = 'draid'
                topology['draid'].append({
                    'disk': z_vdev,
                    'parameters': {
                        'children': len(children),
                        'draid_parity': int(vdev['type'][-1]),
                        'draid_spare_disks': vdev['draid_spare_disks'],
                        'draid_data_disks': vdev['draid_data_disks'],
                        'special_vdev': vdev['root'].lower() == 'special',
                    }
                })
            else:
                z_vdev.type = vdev['type'].lower()
                topology[vdev['root'].lower()].append(z_vdev)
    return topology


def find_vdev(pool, vname):
    """
    Find a vdev in the given `pool` using `vname` looking for
    guid or path

    Returns:
        libzfs.ZFSVdev object
    """
    children = []
    for vdevs in pool.groups.values():
        children += vdevs
        while children:
            child = children.pop()

            if str(vname) == str(child.guid):
                return child

            if child.type == 'disk':
                path = child.path.replace('/dev/', '')
                if path == vname:
                    return child

            children += list(child.children)
