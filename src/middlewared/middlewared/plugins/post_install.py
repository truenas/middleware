import json
import os

import jsonschema

from middlewared.service import Service

PATH = "/data/post_install.json"

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "network_interfaces": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name"],
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "aliases": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["type", "address", "netmask"],
                            "additionalProperties": False,
                            "properties": {
                                "type": {"type": "string"},
                                "address": {"type": "string"},
                                "netmask": {"type": "integer"},
                            },
                        },
                    },
                    "ipv4_dhcp": {"type": "boolean"},
                    "ipv6_auto": {"type": "boolean"},
                },
            },
        },
    },
}


class PostInstallService(Service):

    class Config:
        private = True

    def process(self):
        if os.path.exists(PATH):
            try:
                with open(PATH) as f:
                    data = json.load(f)

                jsonschema.validate(data, SCHEMA)

                self.process_data(data)
            finally:
                os.unlink(PATH)

    def process_data(self, data):
        for interface in data.get("network_interfaces", []):
            try:
                self.middleware.call_sync("interface.update", interface["name"], {
                    "aliases": interface.get("aliases", []),
                    "ipv4_dhcp": interface.get("ipv4_dhcp", False),
                    "ipv6_auto": interface.get("ipv6_auto", False),
                })
            except Exception as e:
                self.logger.warning("Error configuring interface %r from post_install: %r", interface["name"], e)

        self.middleware.call_sync("interface.checkin")


async def setup(middleware):
    try:
        await middleware.call("postinstall.process")
    except Exception:
        middleware.logger.error("Error processing post_install file", exc_info=True)
