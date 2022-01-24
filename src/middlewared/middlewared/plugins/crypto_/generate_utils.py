from middlewared.validators import IpAddress


def normalize_san(san_list: list) -> list:
    # TODO: ADD MORE TYPES WRT RFC'S
    normalized = []
    ip_validator = IpAddress()
    for count, san in enumerate(san_list or []):
        try:
            ip_validator(san)
        except ValueError:
            normalized.append(['DNS', san])
        else:
            normalized.append(['IP', san])

    return normalized
