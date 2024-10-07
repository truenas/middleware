from dataclasses import dataclass
from types import NoneType

from .header import HeaderInfo, validate_and_parse_header


@dataclass(slots=True, frozen=True, kw_only=True)
class Pg80:
    header: HeaderInfo | None
    serial: str | None


def parse_it(file_path: str) -> Pg80:
    header: NoneType = None
    serial: NoneType = None
    page_code: int = 0x80
    with open(file_path, "rb") as f:
        data: memoryview = memoryview(f.read())
        header: HeaderInfo = validate_and_parse_header(data, page_code)
        serial: str = bytes(data[header.header_length :]).decode(
            "ascii", errors="replace"
        )

    return Pg80(header=header, serial=serial)
