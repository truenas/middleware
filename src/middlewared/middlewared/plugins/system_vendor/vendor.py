import json
import os

SENTINEL_FILE_PATH = '/data/.vendor'


def get_vendor() -> str | None:
    with open(SENTINEL_FILE_PATH, 'r') as file:
        return json.load(file).get('name') or None  # Don't return an empty string.


def remove_vendor_file() -> None:
    os.remove(SENTINEL_FILE_PATH)


def is_vendored() -> bool:
    return os.path.isfile(SENTINEL_FILE_PATH)
