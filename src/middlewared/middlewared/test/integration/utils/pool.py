# -*- coding=utf-8 -*-
import logging
import os
import sys

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name

logger = logging.getLogger(__name__)

__all__ = ["pool"]

pool = pool_name
