import os


def write_if_changed(path, data):

    if isinstance(data, str):
        data = data.encode()

    changed = False

    with open(os.open(path, os.O_CREAT | os.O_RDWR), 'wb+') as f:
        f.seek(0)
        current = f.read()
        if current != data:
            changed = True
            f.seek(0)
            f.write(data)
            f.truncate()
        os.fsync(f)

    return changed
