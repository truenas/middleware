# -*- coding=utf-8 -*-
import logging
import re


logger = logging.getLogger(__name__)

__all__ = ['get_cpu_model']


RE_CPU_MODEL = re.compile(r'^model name\s*:\s*(.*)')


def get_cpu_model():
    with open('/proc/cpuinfo', 'r') as f:
        model = RE_CPU_MODEL.search(f.read(), re.M)
        return model.group(1) if model else None
