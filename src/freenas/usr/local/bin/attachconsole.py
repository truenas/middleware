#!/usr/local/bin/python
import sys
import subprocess


def attach_console():
    """attach console.

    Keyword arguments:
    None

    Returns
    None
    """
    devices = subprocess.Popen("fuser {0}".format(
        sys.argv[1]), shell=True, stdout=subprocess.PIPE).stdout.read()
    pids = devices.decode('utf-8').split()

    for pid in pids:
        subprocess.Popen("kill -9 {0}".format(
            pid), shell=True, stdout=subprocess.PIPE).stdout.read()


if __name__ == '__main__':
    """
    usage:
    attachconsole.py /dev/<serial console id>
    """
    attach_console()
