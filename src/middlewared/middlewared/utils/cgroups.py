# -*- coding=utf-8 -*-
def move_to_root_cgroups(pid: int) -> None:
    with open(f"/proc/{pid}/cgroup") as f:
        for line in f.readlines():
            _, _, value = line.strip().split(":")

            if value == "/system.slice/middlewared.service":
                with open("/sys/fs/cgroup/cgroup.procs", "w") as f2:
                    f2.write(f"{pid}\n")
                    break
