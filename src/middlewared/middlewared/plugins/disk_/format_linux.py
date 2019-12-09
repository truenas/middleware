import subprocess

from middlewared.service import CallError, Service

from .format_base import FormatDiskBase


class DiskService(Service, FormatDiskBase):
    pass
