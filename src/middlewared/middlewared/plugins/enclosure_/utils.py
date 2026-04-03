from .constants import DMI_SUFFIXES_TO_REMOVE

__all__ = ("parse_model",)


def parse_model(spn: str) -> str:
    model = spn.removeprefix("TRUENAS-").removeprefix("FREENAS-")
    for suffix in DMI_SUFFIXES_TO_REMOVE:
        model = model.removesuffix(suffix)
    return model
