import typing


def get_interface_name(item: dict, key: str, interface_dict: dict) -> typing.Optional[str]:

    def get_iface_name(iface_key: str, iface: dict) -> typing.Optional[str]:
        iface_id = iface[iface_key]
        if iface_id in interface_dict:
            return interface_dict[iface_id]['int_interface']

    if key == 'interfaces' and isinstance(item, dict) and 'int_interface' in item:
        return item['int_interface']
    elif key == 'bridge':
        return get_iface_name('interface', item)
    elif key == 'vlan' and 'vlan_vint' in item:
        return item['vlan_vint']
    elif key == 'lagg':
        return get_iface_name('lagg_interface', item)
    elif key == 'laggmembers' and 'lagg_interface' in item:
        return item['lagg_interface']


def find_interface_changes(original_datastores: dict, current_datastores: dict) -> typing.List[str]:
    changed_interfaces = set()
    original_items_dict = {}
    current_items_dict = {}
    current_ifaces = {iface['int_interface']: iface for iface in current_datastores.get('interfaces', [])}

    for key in ('interfaces', 'alias', 'bridge', 'vlan', 'lagg', 'laggmembers'):
        original_items_dict[key] = {item['id']: item for item in original_datastores.get(key, [])}
        current_items_dict[key] = {item['id']: item for item in current_datastores.get(key, [])}

        for id_, item in current_items_dict[key].items():
            if id_ in original_items_dict[key] and item != original_items_dict[key][id_]:
                if interface_name := get_interface_name(item, key, current_datastores['interfaces']):
                    changed_interfaces.add(interface_name)

            if key != 'laggmembers':
                continue

            # lagg members is special in the sense that if members have been added/removed, that also points out that
            # lagg interface has changed
            # So we will get added/removed lagg members and add the lagg interface to changed_interfaces
            args = ['laggmembers', current_datastores['interfaces']]
            for lagg_member in set(current_items_dict) - set(original_items_dict):
                if (
                    (interface_name := get_interface_name(*([current_items_dict[lagg_member]] + args))) and
                    interface_name in current_ifaces
                ):
                    changed_interfaces.add(interface_name)

            for lagg_member in set(original_items_dict) - set(current_items_dict):
                if (
                    (interface_name := get_interface_name(*([original_items_dict[lagg_member]] + args))) and
                    interface_name in current_ifaces
                ):
                    changed_interfaces.add(interface_name)

    return list(changed_interfaces)


def retrieve_added_removed_interfaces(
    original_datastores: dict, current_datastores: dict, retrieval_type: str
) -> typing.List[str]:
    original_ifaces = set([iface['int_interface'] for iface in original_datastores.get('interfaces', [])])
    current_ifaces = set([iface['int_interface'] for iface in current_datastores.get('interfaces', [])])
    return list(
        original_ifaces - current_ifaces if retrieval_type == 'removed' else current_ifaces - original_ifaces
    )
