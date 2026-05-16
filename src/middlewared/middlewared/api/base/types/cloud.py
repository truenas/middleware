from types import MappingProxyType
from typing import Literal

__all__ = ["OVHEndpoint", "OVH_ENDPOINTS"]

# OVH API endpoints by region. Source: https://github.com/ovh/python-ovh
# (these values have been stable for years).
OVH_ENDPOINTS = MappingProxyType({
    "ovh-eu": "https://eu.api.ovh.com/1.0",
    "ovh-ca": "https://ca.api.ovh.com/1.0",
    "ovh-us": "https://api.ovhcloud.com/1.0",
    "kimsufi-eu": "https://eu.api.kimsufi.com/1.0",
    "kimsufi-ca": "https://ca.api.kimsufi.com/1.0",
    "soyoustart-eu": "https://eu.api.soyoustart.com/1.0",
    "soyoustart-ca": "https://ca.api.soyoustart.com/1.0",
})

OVHEndpoint = Literal[
    "ovh-eu",
    "ovh-ca",
    "ovh-us",
    "kimsufi-eu",
    "kimsufi-ca",
    "soyoustart-eu",
    "soyoustart-ca",
]
