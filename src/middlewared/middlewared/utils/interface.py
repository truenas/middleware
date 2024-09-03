import contextlib


def get_default_interface() -> str | None:
    data = []
    with contextlib.suppress(FileNotFoundError):
        with open('/proc/net/route', 'r') as f:
            data = [line.split() for line in f.readlines()]

    for entry in filter(lambda i: len(i) == 11, data):
        if entry[1] == '00000000' and entry[1] == entry[7]:
            return entry[0]
