import contextlib

from middlewared.test.integration.utils import call, mock


@contextlib.contextmanager
def fake_disks(disks):
    with mock("disk.get_disks", """
        def mock(self):
            from dataclasses import asdict
            from functools import cached_property
            import inspect
            
            from middlewared.utils.disks_.disk_class import DiskEntry, iterate_disks
            
            def serialize(disk):
                return {
                    **asdict(disk),
                    **{
                        t[0]: getattr(disk, t[0])
                        for t in inspect.getmembers(DiskEntry, lambda v: isinstance(v, cached_property))
                    },
                }

            return [serialize(disk) for disk in iterate_disks()]
    """):
        get_disks = call("disk.get_disks")

    template = get_disks[-1]

    for i, (name, data) in enumerate(disks.items()):
        suffix = f"_fake{i + 1}"
        disk = template.copy()
        disk["identifier"] += suffix
        disk["serial"] += suffix
        disk["name"] = name
        disk["devpath"] = f"/dev/{name}"
        disk.update(**data)
        get_disks.append(disk)

    with mock("disk.get_disks", f"""
        def mock(self):
            from types import SimpleNamespace

            return [SimpleNamespace(**disk) for disk in {get_disks!r}]
    """):
        yield
