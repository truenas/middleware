from functools import cache
from xml.etree import ElementTree

__all__ = ("kbdmap_choices",)


@cache
def kbdmap_choices() -> tuple[tuple[str, str], ...]:
    choices = list()
    for child in (
        ElementTree.parse("/usr/share/X11/xkb/rules/xorg.xml")
        .getroot()
        .findall(".//layoutList/layout")
    ):
        lang: str = child.find("configItem/name").text  # type: ignore[assignment, union-attr]
        desc: str = child.find("configItem/description").text  # type: ignore[assignment, union-attr]
        choices.append((lang, desc))
        for gchild in child.findall("./variantList/variant/configItem"):
            variant: str = gchild.find("name").text  # type: ignore[assignment, union-attr]
            variant_desc: str = gchild.find("description").text  # type: ignore[assignment, union-attr]
            choices.append((f"{lang}.{variant}", variant_desc))
    return tuple(choices)
