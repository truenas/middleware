# -*- coding=utf-8 -*-
import logging
import subprocess

logger = logging.getLogger(__name__)

__all__ = ["run_command_with_user_context"]


def run_command_with_user_context(commandline, user, callback):
    p = subprocess.Popen(["sudo", "-H", "-u", user, "sh", "-c", commandline],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    stdout = b""
    while True:
        line = p.stdout.readline()
        if not line:
            break

        stdout += line
        callback(line)

    p.communicate()

    return subprocess.CompletedProcess(commandline, stdout=stdout, returncode=p.returncode)
