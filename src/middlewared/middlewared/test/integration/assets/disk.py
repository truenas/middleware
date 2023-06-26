import contextlib

from middlewared.test.integration.utils import call, mock


@contextlib.contextmanager
def fake_disks(disks):
    disk_query = call("disk.query")
    template = disk_query[-1]

    for i, (name, data) in enumerate(disks.items()):
        suffix = f"_fake{i + 1}"
        disk = template.copy()
        disk["identifier"] += suffix
        disk["serial"] += suffix
        disk["name"] = name
        disk["devname"] = name
        disk.update(**data)
        disk_query.append(disk)

    with mock("disk.query", return_value=disk_query):
        yield
