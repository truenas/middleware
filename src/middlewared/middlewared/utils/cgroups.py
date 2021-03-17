# -*- coding=utf-8 -*-
def move_to_root_cgroups(pid):
    with open(f"/proc/{pid}/cgroup") as f:
        for line in f.readlines():
            _, names, value = line.strip().split(":")

            if value == "/system.slice/middlewared.service":
                for name in names.split(","):
                    new_name = {
                        "name=systemd": "systemd",
                        "": "unified",
                    }.get(name, name)
                    with open(f"/sys/fs/cgroup/{new_name}/cgroup.procs", "w") as f2:
                        f2.write(f"{pid}\n")
