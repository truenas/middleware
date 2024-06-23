import os
import subprocess

from middlewared.plugins.docker.state_utils import IX_APPS_MOUNT_PATH  # noqa


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
