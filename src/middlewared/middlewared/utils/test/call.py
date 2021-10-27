# -*- coding=utf-8 -*-
from .client import client

__all__ = ["call"]


def call(*args, **kwargs):
    with client() as c:
        return c.call(*args, **kwargs)
