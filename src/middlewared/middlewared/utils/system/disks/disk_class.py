from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Disk:
    name: str
    serial: str
    lunid: str

    @property
    def identifier(self):
        if self.serial and self.lunid:
            return f"{{serial_identier}}{self.serial}{self.lunid}"
        return f"{{devicename}}{self.name}"
