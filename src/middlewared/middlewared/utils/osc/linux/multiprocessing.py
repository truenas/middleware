from middlewared.utils.prctl import set_pdeath_sig

__all__ = ["die_with_parent"]


def die_with_parent():
    set_pdeath_sig()
