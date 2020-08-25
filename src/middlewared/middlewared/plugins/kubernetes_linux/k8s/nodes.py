from kubernetes_asyncio.client import V1Taint

from middlewared.service import CallError


async def get_node_from_name(client, node_name):
    if not node_name:
        raise CallError(f'No node name / node object specified.')
    node_object = await client.list_node_with_http_info(field_selector=f'metadata.name={node_name}')
    if not node_object:
        raise CallError(f'Unable to find "{node_name}" node.')
    else:
        return node_object[0]


async def add_taint(client, taint_dict, node_name=None, node_object=None):
    for k in ('key', 'effect'):
        assert k in taint_dict

    if not node_object:
        node_object = get_node_from_name(client, node_name)

    node_object.spec.taints.append(V1Taint(**taint_dict))
    client.patch_node(name=node_object.metadata.name, body=node_object)
