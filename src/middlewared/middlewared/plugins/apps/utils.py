import os
import subprocess

from middlewared.plugins.docker.state_utils import DatasetDefaults, IX_APPS_MOUNT_PATH  # noqa


PROJECT_PREFIX = 'ix-'
UPGRADE_SNAP_PREFIX = 'ix-app-upgrade-'


def upgrade_summary_info(app: dict) -> dict:
    return {
        'latest_version': app['version'],
        'latest_human_version': app['human_version'],
        'upgrade_version': app['version'],
        'upgrade_human_version': app['human_version'],
        'changelog': 'Image updates are available for this app',
        'available_versions_for_upgrade': [],
    }


def get_upgrade_snap_name(app_name: str, app_version: str) -> str:
    return f'{UPGRADE_SNAP_PREFIX}{app_name}-{app_version}'


def get_app_stop_cache_key(app_name: str) -> str:
    return f'app_stop_{app_name}'


def run(*args, **kwargs) -> subprocess.CompletedProcess:
    shell = isinstance(args[0], str)
    if isinstance(args[0], list):
        args = tuple(args[0])
    kwargs.setdefault('stdout', subprocess.PIPE)
    kwargs.setdefault('stderr', subprocess.PIPE)
    kwargs.setdefault('timeout', 60)
    check = kwargs.pop('check', False)
    env = kwargs.pop('env', None) or os.environ

    proc = subprocess.Popen(
        args, stdout=kwargs['stdout'], stderr=kwargs['stderr'], shell=shell,
        encoding='utf8', errors='ignore', env=env,
    )
    stdout = ''
    try:
        stdout, stderr = proc.communicate(timeout=kwargs['timeout'])
    except subprocess.TimeoutExpired:
        proc.kill()
        stderr = 'Timed out waiting for response'
        proc.returncode = -1

    cp = subprocess.CompletedProcess(args, proc.returncode, stdout=stdout, stderr=stderr)
    if check and cp.returncode:
        raise subprocess.CalledProcessError(cp.returncode, cp.args, stderr=stderr)
    return cp
