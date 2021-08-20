# -*- coding=utf-8 -*-
import logging
import re
import subprocess
import sysctl

logger = logging.getLogger(__name__)

__all__ = ['get_cpu_model']


RE_PORT = re.compile(r'([0-9a-fA-Fx]+).*\((uart[0-9])+\)')


def get_cpu_model():
    return sysctl.filter('hw.model')[0].value


def serial_port_choices():
    cp = subprocess.Popen(
        "/usr/sbin/devinfo -u | grep -A 99999 '^I/O ports:' | grep -E '*([0-9a-fA-Fx]+).*\\(uart[0-9]+\\)'",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
    )
    stdout, stderr = cp.communicate()
    return [
        {
            'name': e[1],
            'start': e[0],
        } for e in RE_PORT.findall(stdout.decode(errors='ignore'))
    ]
