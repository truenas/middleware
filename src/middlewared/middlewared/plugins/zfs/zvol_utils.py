import os
import re

__all__ = (
    "get_zvol_attachments_impl",
    "unlocked_zvols_fast_impl",
)

ZD_PARTITION = re.compile(r"zd[0-9]+p[0-9]+$")


def zvol_name_to_path(name: str) -> str:
    return os.path.join("/dev/zvol", name.replace(" ", "+"))


def zvol_path_to_name(path: str) -> str:
    # splice at 10 chars because "/dev/zvol/"
    return path[10:].replace("+", " ") or path


def unlocked_zvols_fast_impl(options=None, data=None):
    """
    Get zvol information from /sys/block and /dev/zvol.
    This is quite a bit faster than using truenas_pylibzfs.

    supported options:
    `SIZE` - size of zvol
    `DEVID` - the device id of the zvol
    `RO` - whether zvol is flagged as ro (snapshot)
    `ATTACHMENT` - where zvol is currently being used

    If 'ATTACHMENT' is used, then dict of attachemnts
    should be provided under `data` key `attachments`
    """
    data = data or dict()
    options = options or list()
    out = dict()
    for root, _, files in os.walk("/dev/zvol"):
        if not files:
            continue

        for file in files:
            path = f"{root}/{file}"
            zvol_name = zvol_path_to_name(path)
            try:
                dev_name = os.readlink(path).split("/")[-1]
            except Exception:
                # this happens if the file is a regular file
                # saw this happend when a user logged into a system
                # via ssh and tried to "copy" a zvol using "dd" on
                # the cli and made a typo in the command. This created
                # a regular file. When we readlink() that file, it
                # crashed with OSError 22 Invalid Argument so we just
                # skip this file
                continue

            if ZD_PARTITION.match(dev_name):
                continue

            out.update(
                {
                    zvol_name: {
                        "path": path,
                        "name": zvol_name,
                        "dev": dev_name,
                    }
                }
            )

            if "SIZE" in options:
                with open(f"/sys/block/{dev_name}/size", "r") as f:
                    out[zvol_name]["size"] = int(f.readline()[:-1]) * 512

            if "DEVID" in options:
                with open(f"/sys/block/{dev_name}/dev", "r") as f:
                    out[zvol_name]["devid"] = f.readline()[:-1]

            if "RO" in options:
                with open(f"/sys/block/{dev_name}/ro", "r") as f:
                    out[zvol_name]["ro"] = f.readline()[:-1] == "1"

            if "ATTACHMENT" in options:
                out[zvol_name]["attachment"] = None
                for method, attachment in data.get("attachments", {}).items():
                    val = attachment.pop(zvol_name, None)
                    if val is not None:
                        out[zvol_name]["attachment"] = {"method": method, "data": val}
                        break

    return out


def get_zvol_attachments_impl(middleware):
    att_data = {
        "iscsi.extent.query": dict(),
        "vm.devices.query": dict(),
        "nvmet.namespace.query": dict(),
    }
    for i in middleware.call_sync(
        "iscsi.extent.query",
        [("type", "=", "DISK")],
        {"select": ["path", "type"]},
    ):
        ip = zvol_path_to_name(f"/dev/{i['path']}")
        att_data["iscsi.extent.query"][ip] = i

    for v in middleware.call_sync("vm.device.query", [["dtype", "=", "DISK"]]):
        vp = zvol_path_to_name(v["attributes"]["path"])
        att_data["vm.devices.query"][vp] = v

    for n in middleware.call_sync(
        "nvmet.namespace.query",
        [["device_type", "=", "ZVOL"]],
        {"select": ["device_path"]},
    ):
        np = zvol_path_to_name(f"/dev/{n['device_path']}")
        att_data["nvmet.namespace.query"][np] = n

    return att_data
