import asyncio
import cProfile
import io
import pstats
from pstats import SortKey
from typing import Any, Callable, Coroutine, ParamSpec, overload


# Preserve order of args and kwargs with ParamSpec
P = ParamSpec('P')


# First matching overload is chosen
@overload
def profile_wrap(func: Callable[P, Coroutine]) -> Callable[P, Coroutine[None, None, str]]: ...


@overload
def profile_wrap(func: Callable[P, Any]) -> Callable[P, str]: ...


def profile_wrap(func: Callable[P, Any]) -> Callable[P, Coroutine[None, None, str]] | Callable[P, str]:
    if asyncio.iscoroutinefunction(func):
        async def wrapper(*args, **kwargs):
            pr = cProfile.Profile()
            pr.enable()
            rv = await func(*args, **kwargs)
            pr.disable()
            s = io.StringIO()
            pstats.Stats(pr, stream=s).sort_stats(SortKey.CUMULATIVE).print_stats()
            return s.getvalue() + '\n' + str(rv)
    else:
        def wrapper(*args, **kwargs):
            pr = cProfile.Profile()
            pr.enable()
            rv = func(*args, **kwargs)
            pr.disable()
            s = io.StringIO()
            pstats.Stats(pr, stream=s).sort_stats(SortKey.CUMULATIVE).print_stats()
            return s.getvalue() + '\n' + str(rv)
    return wrapper
