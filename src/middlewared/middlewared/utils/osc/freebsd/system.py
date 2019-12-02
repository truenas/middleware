# -*- coding=utf-8 -*-
import logging
import sysctl

logger = logging.getLogger(__name__)

__all__ = ['get_cpu_model']


def get_cpu_model():
    return sysctl.filter('hw.model')[0].value
