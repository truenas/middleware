#!/usr/local/bin/python3

import os

from middlewared.client import Client


def main():
    device = os.environ.get("SMARTD_DEVICE")
    if device is None:
        return

    message = os.environ.get("SMARTD_MESSAGE")
    if message is None:
        return

    with Client() as c:
        multipath = c.call(
            "disk.query",
            ["OR", [["name", "=", device], ["multipath_member", "=", device]]],
            {"get": True},
        )
        if multipath["multipath_name"]:
            device = multipath["multipath_name"]

        c.call("alert.oneshot_create", "SMART", {"device": device, "message": message})


if __name__ == "__main__":
    main()
