# -*- coding=utf-8 -*-
import contextlib
import textwrap

from .client import client

__all__ = ["mock"]


@contextlib.contextmanager
def mock(method, declaration="", **kwargs):
    """
    Context manager that temporarily replaces specified middleware `method` with a mock.

    This only works for method calls dispatched with `self.middleware.call` or `self.middleware.call_sync`. Direct class
    method calls (e.g. `self.get_disk_from_partition(...)`) will not be affected.

    :param method: Method name to replace

    :param return_value: The value returned when the mock is called.

    :param declaration: A string, containing python function declaration for mock. Function should be named `mock`,
        can be normal function or `async` and must accept `self` argument and all other arguments the function being
        replaced accepts. No `@accepts`, `@job` or other decorators are required, but if a method being replaced is a
        job, then mock signature must also accept `job` argument.
    """
    if declaration and kwargs:
        raise ValueError("Mock `declaration` is not allowed with kwargs")
    elif declaration:
        arg = textwrap.dedent(declaration)
    else:
        arg = kwargs

    with client() as c:
        c.call("test.set_mock", method, arg)

    try:
        yield
    finally:
        with client() as c:
            c.call("test.remove_mock", method)
