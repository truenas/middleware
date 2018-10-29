# -*- coding=utf-8 -*-
import logging
import os

logger = logging.getLogger(__name__)

__all__ = ["normpath"]


def normpath(s):
    return os.path.normpath(s.strip().strip("/").strip())
