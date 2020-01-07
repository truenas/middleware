# -*- coding=utf-8 -*-
import logging

import prctl

logger = logging.getLogger(__name__)

__all__ = ["set_thread_name"]


def set_thread_name(name):
    prctl.set_name(name)
