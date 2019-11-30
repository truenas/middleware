# -*- coding=utf-8 -*-
import logging
import sysctl

logger = logging.getLogger(__name__)

__all__ = ['cpu_model']


def cpu_model():
    return sysctl.filter('hw.model')[0].value
