from typing import Iterator

OATH_FILE = '/etc/users.oath'


def iter_oath_users() -> Iterator[str]:
    with open(OATH_FILE, 'r') as f:
        for line in f:
            if not line:
                continue

            yield line.split('\t')[1].strip()
