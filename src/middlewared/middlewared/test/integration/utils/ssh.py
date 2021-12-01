# -*- coding=utf-8 -*-
import logging
import os
import sys

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import user, password, ip
from functions import SSH_TEST

logger = logging.getLogger(__name__)

__all__ = ["ssh"]


def ssh(command):
    result = SSH_TEST(command, user, password, ip)
    assert result["result"] is True, f"stdout: {result['output']}\nstderr: {result['stderr']}"
    return result["output"]
