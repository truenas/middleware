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


def delete_image(image_id: str, force: bool = False):
    with get_docker_client() as client:
        try:
            client.images.remove(image=image_id, force=force)
        except docker.errors.ImageNotFound:
            raise CallError(f'{image_id!r} image not found')
        except docker.errors.APIError as e:
            raise CallError(f'Failed to delete {image_id!r} image: {e!s}')
