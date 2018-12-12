# -*- coding=utf-8 -*-
import logging
import os

logger = logging.getLogger(__name__)

__all__ = ["is_child"]


def is_child(child: str, parent: str):
    rel = os.path.relpath(child, parent)
    return rel == "." or not rel.startswith("..")
