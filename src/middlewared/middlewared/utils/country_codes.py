from functools import cache
from json import load

__all__ = ("get_iso_3166_2_country_codes",)


@cache
def get_iso_3166_2_country_codes() -> dict[str, str]:
    with open("/usr/share/iso-codes/json/iso_3166-1.json") as f:
        return {i["alpha_2"]: i["name"] for i in load(f)["3166-1"]}
