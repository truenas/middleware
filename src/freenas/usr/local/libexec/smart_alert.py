#!/usr/bin/env python3

import os

from truenas_api_client import Client


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
        dev_name = device.removeprefix("/dev/")
        info = c.call("device.get_disk", dev_name, False, True)
        if info is not None and (serial := info['serial']):
            device = " ".join([device, f"({serial!r})"])

        c.call("alert.oneshot_create", "SMART", {"device": device, "message": message})


if __name__ == "__main__":
    main()
