from functools import cache
from json import load

__all__ = ("get_country_codes",)


@cache
def get_country_codes() -> tuple[tuple[str, str], ...]:
    """Return the ISO 3166-1 alpha 2 code as the key and the
    English short name (used in ISO 3166/MA) of the country
    as the value (i.e {"US": "United States of America", ...})"""
    with open("/usr/share/iso-codes/json/iso_3166-1.json") as f:
        data = load(f)
        return tuple((i["alpha_2"], i["name"]) for i in data["3166-1"])
