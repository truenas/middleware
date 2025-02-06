import json
import os

from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.service import Service


SENTINEL_FILE_PATH = '/data/.vendor'


def get_vendor() -> str | None:
    with open(SENTINEL_FILE_PATH, 'r') as file:
        return json.load(file).get('name') or None  # Don't return an empty string.


class VendorNameArgs(BaseModel):
    pass


class VendorNameResult(BaseModel):
    result: str | None


class UnvendorArgs(BaseModel):
    pass


class UnvendorResult(BaseModel):
    result: None


class IsVendoredArgs(BaseModel):
    pass


class IsVendoredResult(BaseModel):
    result: bool


class VendorService(Service):

    class Config:
        namespace = 'system.vendor'
        cli_private = True

    @api_method(VendorNameArgs, VendorNameResult, private=True)
    def name(self) -> str | None:
        try:
            return get_vendor()
        except FileNotFoundError:
            pass
        except json.JSONDecodeError:
            self.logger.exception('Can\'t retrieve vendor name: %r is not proper JSON format', SENTINEL_FILE_PATH)
        except Exception:
            self.logger.exception('Unexpected error while reading %r', SENTINEL_FILE_PATH)

    @api_method(UnvendorArgs, UnvendorResult, private=True)
    def unvendor(self):
        try:
            os.remove(SENTINEL_FILE_PATH)
        except FileNotFoundError:
            pass
        except Exception:
            self.logger.exception('Unexpected error attempting to remove %r', SENTINEL_FILE_PATH)

        self.middleware.call_sync('etc.generate', 'grub')

    @api_method(IsVendoredArgs, IsVendoredResult, private=True)
    def is_vendored(self):
        return os.path.isfile(SENTINEL_FILE_PATH)
