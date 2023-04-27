import contextlib
import ctypes
import enum
import signal

__all__ = ['set_name', 'set_pdeath_sig']


class Prctl(enum.IntEnum):
    # from linux/prctl.h
    SET_PDEATHSIG = 1
    SET_NAME = 15


@contextlib.contextmanager
def load_libc():
    libc = None
    try:
        libc = ctypes.CDLL('libc.so.6')
        yield libc
    finally:
        # probably not needed but rather be safe than sorry
        del libc


def set_name(name):
    if isinstance(name, str):
        name = name.encode()

    with load_libc() as libc:
        return libc.prctl(Prctl.SET_NAME.value, ctypes.c_char_p(name), 0, 0, 0)


def set_pdeath_sig(sig=signal.SIGKILL):
    with load_libc() as libc:
        libc.prctl(Prctl.SET_PDEATHSIG.value, signal.Signals(sig).value, 0, 0, 0)
