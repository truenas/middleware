# -*- coding=utf-8 -*-
import logging
import re
import subprocess

logger = logging.getLogger(__name__)

__all__ = ['get_cpu_model']

RE_CPU_MODEL = re.compile(r'^model name\s*:\s*(.*)', flags=re.M)
RE_PORT = re.compile(r'(ttyS\d+) at I/O (\S+)')


def get_cpu_model():
    with open('/proc/cpuinfo', 'r') as f:
        model = RE_CPU_MODEL.search(f.read())
        return model.group(1) if model else None


def serial_port_choices():
    cp = subprocess.Popen('dmesg | grep ttyS', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = cp.communicate()
    return {e[0]: e[1] for e in RE_PORT.findall(stdout.decode(errors='ignore'))}
