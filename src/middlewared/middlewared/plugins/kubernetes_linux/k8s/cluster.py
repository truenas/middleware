import errno
import os

from kubernetes_asyncio import utils

from middlewared.service import CallError


async def create_from_yaml(api_client, yaml_file_path):
    if not os.path.exists(yaml_file_path):
        raise CallError(f'{yaml_file_path!r} does not exist', errno=errno.ENOENT)

    await utils.create_from_yaml(api_client, yaml_file_path)
