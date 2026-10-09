# -*- coding=utf-8 -*-
from .client import client, truenas_server

__all__ = ["call"]


def call(*args, reset_rate_limit=True, **kwargs):
    if not (client_kwargs := kwargs.pop("client_kwargs", {})) and truenas_server.ip:
        return truenas_server.client.call(*args, **kwargs)

    with client(**client_kwargs, reset_rate_limit=reset_rate_limit) as c:
        return c.call(*args, **kwargs)
