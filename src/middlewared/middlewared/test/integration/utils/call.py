# -*- coding=utf-8 -*-
from .client import client

__all__ = ["call"]


def call(*args, **kwargs):
    client_args = kwargs.pop('client_args', {})
    with client(**client_args) as c:
        return c.call(*args, **kwargs)
