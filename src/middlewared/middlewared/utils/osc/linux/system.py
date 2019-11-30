# -*- coding=utf-8 -*-
import logging
import re
import subprocess


logger = logging.getLogger(__name__)

__all__ = ['cpu_model']


RE_CPU_MODEL = re.compile(r'Model name:\s*(.*)')


def cpu_model():
    cp = subprocess.Popen('lscpu', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = cp.communicate()
    model = RE_CPU_MODEL.findall(stdout)
    return model[0].strip() if model else None
