# -*- coding=utf-8 -*-
import logging
import os

logger = logging.getLogger(__name__)

__all__ = ["zvol_name_to_path", "zvol_path_to_name"]


def zvol_name_to_path(name):
    return os.path.join("/dev/zvol", name.replace(" ", "+"))


def zvol_path_to_name(path):
    if not path.startswith("/dev/zvol/"):
        raise ValueError(f"Invalid zvol path: {path!r}")

    return path[len("/dev/zvol/"):].replace("+", " ")
