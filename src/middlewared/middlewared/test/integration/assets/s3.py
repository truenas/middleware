# -*- coding=utf-8 -*-
import contextlib
import logging
from types import SimpleNamespace

from middlewared.test.integration.utils import call

logger = logging.getLogger(__name__)

__all__ = ["s3_server"]


@contextlib.contextmanager
def s3_server(dataset):
    access_key = "A" * 8
    secret_key = "B" * 16
    call("s3.update", {
        "bindip": "0.0.0.0",
        "bindport": 9000,
        "access_key": access_key,
        "secret_key": secret_key,
        "browser": True,
        "storage_path": f"/mnt/{dataset}",
    })
    assert call("service.start", "s3")

    try:
        yield SimpleNamespace(access_key=access_key, secret_key=secret_key)
    finally:
        call("service.stop", "s3")
