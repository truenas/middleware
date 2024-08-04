import typing

import docker.errors

from middlewared.service import CallError

from .casing import convert_case_for_dict_or_list
from .utils import get_docker_client


def list_images() -> list[dict]:
    with get_docker_client() as client:
        return [
            image for image in map(
                lambda i: convert_case_for_dict_or_list(i.attrs), client.images.list()
            )
        ]


def pull_image(
    image_tag: str, callback: typing.Callable = None, username: str | None = None, password: str | None = None
):
    if username and not password:
        raise CallError('Password is required when username is provided')

    if password and not username:
        raise CallError('Username is required when password is provided')

    auth_config = {
        'username': username,
        'password': password,
    } if username else None

    with get_docker_client() as client:
        try:
            response = client.api.pull(image_tag, auth_config=auth_config, stream=True, decode=True)
            for line in response:
                if callback:
                    callback(line)
        except docker.errors.APIError as e:
            raise CallError(f'Failed to pull {image_tag!r} image: {e!s}')


def delete_image(image_id: str, force: bool = False):
    with get_docker_client() as client:
        try:
            client.images.remove(image=image_id, force=force)
        except docker.errors.ImageNotFound:
            raise CallError(f'{image_id!r} image not found')
        except docker.errors.APIError as e:
            raise CallError(f'Failed to delete {image_id!r} image: {e!s}')
