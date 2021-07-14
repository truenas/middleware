#!/usr/bin/env python3

import os

from middlewared.client import Client


def main():
    device = os.environ.get("SMARTD_DEVICE")
    if device is None:
        return

    message = os.environ.get("SMARTD_MESSAGE")
    if message is None:
        return

    if "nvme" in device and "number of Error Log entries increased" in message:
        return

    with Client() as c:
        c.call("alert.oneshot_create", "SMART", {"device": device, "message": message})


if __name__ == "__main__":
    main()
