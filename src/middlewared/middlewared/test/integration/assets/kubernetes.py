import contextlib
import typing

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def backup(backup_name: typing.Optional[str] = None):
    backup_name = call('kubernetes.backup_chart_releases', backup_name, job=True)
    try:
        yield backup_name
    finally:
        call('kubernetes.delete_backup', backup_name)
