# -*- coding=utf-8 -*-
import logging
import signal

import prctl

logger = logging.getLogger(__name__)

__all__ = ["die_with_parent"]


def die_with_parent():
    prctl.set_pdeathsig(signal.SIGKILL)
