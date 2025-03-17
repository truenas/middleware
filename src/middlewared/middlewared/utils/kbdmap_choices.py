from functools import cache
from xml.etree import ElementTree

__all__ = ("kbdmap_choices",)


@cache
def kbdmap_choices() -> tuple[tuple[str, str]]:
    choices = list()
    for child in (
        ElementTree.parse("/usr/share/X11/xkb/rules/xorg.xml")
        .getroot()
        .findall(".//layoutList/layout")
    ):
        lang = child.find("configItem/name").text
        desc = child.find("configItem/description").text
        choices.append((lang, desc))
        for gchild in child.findall("./variantList/variant/configItem"):
            variant = gchild.find("name").text
            variant_desc = gchild.find("description").text
            choices.append((f"{lang}.{variant}", variant_desc))
    return tuple(choices)
