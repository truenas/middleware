# -*- coding=utf-8 -*-
import logging

from middlewared.utils.osc.common.os import close_fds

logger = logging.getLogger(__name__)

__all__ = ["close_fds"]
