import asyncio
import cProfile
import io
import pstats
from pstats import SortKey


def profile_wrap(func):
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
