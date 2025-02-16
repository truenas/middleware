import json
import os

import jsonschema

from middlewared.service import Service

PATH = "/data/post-install.json"

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
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
        "tnc_config": {
            "type": "object",
            "properties": {
                "jwt_token": {"oneOf": [{"type": "null"}, {"type": "string"}]},
                "registration_details": {"type": "object", "additionalProperties": True},
                "ips": {"type": "array", "items": {"type": "string"}},
                "csr_public_key": {"oneOf": [{"type": "null"}, {"type": "string"}]},
                "certificate_public_key": {"oneOf": [{"type": "null"}, {"type": "string"}]},
                "certificate_private_key": {"oneOf": [{"type": "null"}, {"type": "string"}]},
                "account_service_base_url": {"type": "string"},
                "leca_service_base_url": {"type": "string"},
                "tnc_base_url": {"type": "string"},
                "claim_token": {"oneOf": [{"type": "null"}, {"type": "string"}]},
                "claim_token_expiration": {"oneOf": [{"type": "null"}, {"type": "number"}]},
                "registration_finalization_expiration": {"oneOf": [{"type": "null"}, {"type": "number"}]},
                "system_id": {"oneOf": [{"type": "null"}, {"type": "string"}]},
                "truenas_version": {"oneOf": [{"type": "null"}, {"type": "string"}]},
                "initialization_in_progress": {"enabled": {"type": "boolean"}},
                "initialization_completed": {"enabled": {"type": "boolean"}},
                "initialization_error": {"oneOf": [{"type": "null"}, {"type": "string"}]},
                "enabled": {"type": "boolean"},
            },
            "required": [
                "jwt_token", "registration_details", "ips", "certificate_public_key", "certificate_private_key",
                "csr_public_key", "account_service_base_url", "leca_service_base_url", "tnc_base_url", "claim_token",
                "registration_finalization_expiration", "enabled", "systemd_id", "truenas_version",
                "initialization_in_progress", "initialization_completed", "initialization_error",
            ],
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
        self.middleware.call_sync("tn_connect.post_install.process", data)
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
