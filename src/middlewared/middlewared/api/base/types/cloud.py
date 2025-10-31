from typing import Literal

from lexicon.providers.ovh import ENDPOINTS

__all__ = ["OVHEndpoint"]

OVHEndpoint = Literal[tuple(ENDPOINTS.keys())]
