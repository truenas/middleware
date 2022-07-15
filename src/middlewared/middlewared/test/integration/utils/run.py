import os
import subprocess

from typing_extensions import ParamSpec


P = ParamSpec('P')


class RunOnRunnerException(Exception):
    pass


def run_on_runner(*args: P.args, **kwargs: P.kwargs) -> subprocess.CompletedProcess:
    if isinstance(args[0], list):
        args = tuple(args[0])
    kwargs.setdefault('stdout', subprocess.PIPE)
    kwargs.setdefault('stderr', subprocess.PIPE)
    exception_message = kwargs.pop('exception_msg', None)
    check = kwargs.pop('check', True)
    shell = kwargs.pop('shell', False)
    log = kwargs.pop('log', True)
    env = kwargs.pop('env', None) or os.environ

    proc = subprocess.Popen(
        args, stdout=kwargs['stdout'], stderr=kwargs['stderr'], shell=shell, env=env, encoding='utf8', errors='ignore'
    )
    stdout, stderr = proc.communicate()

    cp = subprocess.CompletedProcess(args, proc.returncode, stdout=stdout, stderr=stderr)
    if check:
        error_str = exception_message or stderr or ''
        if cp.returncode:
            raise RunOnRunnerException(
                f'Command {" ".join(args) if isinstance(args, list) else args!r} returned exit code '
                f'{cp.returncode}' + (f' ({error_str})' if error_str else '')
            )
    return cp
