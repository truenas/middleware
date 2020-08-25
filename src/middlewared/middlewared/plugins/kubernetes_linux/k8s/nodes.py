from middlewared.service import CallError


async def get_node_from_name(api_client, node_name, node_object):
    if node_object:
        return node_object
    if not node_name:
        raise CallError(f'No node name / node object specified.')
    node_object = await api_client.list_node_with_http_info(field_selector=f'metadata.name={node_name}')
    if not node_object:
        raise CallError(f'Unable to find "{node_name}" node.')
    else:
        return node_object[0].items[0]


async def add_taint(api_client, taint_dict, node_name=None, node_object=None):
    for k in ('key', 'effect'):
        assert k in taint_dict

    node_object = await get_node_from_name(api_client, node_name, node_object)

    existing_taints = [t.to_dict() for t in (node_object.spec.taints or [])]
    await api_client.patch_node(
        name=node_object.metadata.name, body={'spec': {'taints': existing_taints + [taint_dict]}}
    )


async def remove_taint(api_client, taint_key, node_name=None, node_object=None):
    node_object = await get_node_from_name(api_client, node_name, node_object)
    taints = node_object.spec.taints or []

    for index, taint in enumerate(taints):
        if taint.key == taint_key:
            found_index = index
            break
    else:
        raise CallError(f'Unable to find taint with "{taint_key}" key')

    taints.pop(found_index)
    await api_client.patch_node(name=node_object.metadata.name, body={'spec': {'taints': taints}})
