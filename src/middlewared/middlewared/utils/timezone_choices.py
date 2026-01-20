from functools import cache

__all__ = ("tz_choices",)


@cache
def tz_choices() -> tuple[tuple[str, str], ...]:
    # Logic deduced from what timedatectl list-timezones does
    tz: list[tuple[str, str]] = list()
    with open("/usr/share/zoneinfo/tzdata.zi") as f:
        for line in filter(lambda x: x[0] in ("Z", "L"), f):
            index = 1 if line[0] == "Z" else 2
            tz_choice = line.split()[index].strip()
            tz.append((tz_choice, tz_choice))
    return tuple(tz)
