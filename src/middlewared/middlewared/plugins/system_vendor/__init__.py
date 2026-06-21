import json

from middlewared.service import Service

from . import vendor as _vendor

__all__ = ('VendorService',)


class VendorService(Service):

    class Config:
        namespace = 'system.vendor'
        private = True

    def name(self) -> str | None:
        try:
            return _vendor.get_vendor()
        except FileNotFoundError:
            pass
        except json.JSONDecodeError:
            self.logger.exception(
                "Can't retrieve vendor name: %r is not proper JSON format", _vendor.SENTINEL_FILE_PATH
            )
        except Exception:
            self.logger.exception('Unexpected error while reading %r', _vendor.SENTINEL_FILE_PATH)
        return None

    def unvendor(self) -> None:
        try:
            _vendor.remove_vendor_file()
        except FileNotFoundError:
            pass
        except Exception:
            self.logger.exception('Unexpected error attempting to remove %r', _vendor.SENTINEL_FILE_PATH)

        self.middleware.call_sync('etc.generate', 'grub')

    def is_vendored(self) -> bool:
        return _vendor.is_vendored()
