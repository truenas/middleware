import os

from middlewared.api import api_method
from middlewared.api.current import VendorNameArgs, VendorNameResult, UnvendorArgs, UnvendorResult
from middlewared.service import Service


SENTINEL_FILE_PATH = '/data/.vendor'


class VendorService(Service):

    @api_method(VendorNameArgs, VendorNameResult, private=True)
    def name(self) -> str | None:
        try:
            with open(SENTINEL_FILE_PATH, 'r') as file:
                if contents := file.read():
                    return contents
        except FileNotFoundError:
            return None

    @api_method(UnvendorArgs, UnvendorResult, private=True)
    def unvendor(self):
        try:
            os.remove(SENTINEL_FILE_PATH)
        except FileNotFoundError:
            return None
