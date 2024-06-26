# -*- coding=utf-8 -*-
from .client import client, truenas_server

__all__ = ["call"]


def call(*args, **kwargs):
    if not (client_kwargs := kwargs.pop("client_kwargs", {})) and truenas_server.ip:
        raise ValueError('went to optimized client') 

    with client(client_kwargs) as c:
        return c.call(*args, **kwargs)
