import os

from middlewared.service import private, Service


SENTINEL_FILE_PATH = '/data/.vendor'


class VendorService(Service):

    @private
    def name(self) -> str | None:
        try:
            with open(SENTINEL_FILE_PATH, 'r') as file:
                if contents := file.read():
                    return contents
        except FileNotFoundError:
            return None

    @private
    def unvendor(self):
        try:
            os.remove(SENTINEL_FILE_PATH)
        except FileNotFoundError:
            return None
