import subprocess

__all__ = ["bitmask_to_set", "INTERNAL_INTERFACES", "run"]


# Keep this as an immutable type since this
# is used all over the place and we don't want
# the contents to change
INTERNAL_INTERFACES = (
    "wg",
    "lo",
    "tun",
    "tap",
    "docker",
    "veth",
    "vnet",
    "ix",
    "tailscale",
    "mac",  # macvtap AND mac (latter being macvlan)
    "truenasbr",
)


def bitmask_to_set(n, enumeration):
    return {e for e in enumeration if n & e.value}


def run(*args, **kwargs):
    kwargs.setdefault("check", True)
    kwargs.setdefault("stdout", subprocess.PIPE)
    kwargs.setdefault("stderr", subprocess.PIPE)
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "ignore")
    return subprocess.run(*args, **kwargs)
