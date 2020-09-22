from middlewared.service import CallError

from .utils import NODE_NAME


async def get_node(api_client, node_object=None):
    if node_object:
        return node_object
    node_object = await api_client.list_node_with_http_info(field_selector=f'metadata.name={NODE_NAME}')
    if not node_object[0].items:
        raise CallError(f'Unable to find "{NODE_NAME}" node.')
    else:
        return node_object[0].items[0]


async def add_taint(api_client, taint_dict, node_object=None):
    for k in ('key', 'effect'):
        assert k in taint_dict

    node_object = await get_node(api_client, node_object)

    existing_taints = []
    for taint in map(lambda t: t.to_dict(), (node_object.spec.taints or [])):
        if all(taint[k] == taint_dict[k] for k in ('key', 'effect', 'value')):
            return
        existing_taints.append(taint)

    await api_client.patch_node(
        name=node_object.metadata.name, body={'spec': {'taints': existing_taints + [taint_dict]}}
    )


async def remove_taint(api_client, taint_key, node_object=None):
    node_object = await get_node(api_client, node_object)
    taints = node_object.spec.taints or []

    indexes = []
    for index, taint in enumerate(taints):
        if taint.key == taint_key:
            indexes.append(index)

    if not indexes:
        raise CallError(f'Unable to find taint with "{taint_key}" key')

    for index in sorted(indexes, reverse=True):
        taints.pop(index)

    await api_client.patch_node(name=node_object.metadata.name, body={'spec': {'taints': taints}})
