from .casing import convert_case_for_dict_or_list
from .utils import get_docker_client


def list_images() -> list[dict]:
    with get_docker_client() as client:
        return [
            image for image in map(
                lambda i: convert_case_for_dict_or_list(i.attrs), client.images.list()
            )
        ]
