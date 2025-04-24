from functools import partial
from string import digits, ascii_uppercase, ascii_lowercase, punctuation


__all__ = ("passwd_complexity_validator",)

ALLOWED_TYPES = (
    "ASCII_LOWER",
    "ASCII_UPPER",
    "SPECIAL",
    "DIGIT",
)


def __complexity_impl(
    value: str,
    *,
    required_types: list[str] | None,
    required_cnt: int,
    min_length: int,
    max_length: int,
) -> str:
    passwd_length = len(value)
    if passwd_length < min_length:
        raise ValueError(f"Length of password must be at least {min_length} chars")
    elif passwd_length > max_length:
        raise ValueError(f"Length of password can not be more than {max_length} chars")

    cnt = 0
    reqs = []
    errstr = ""
    if value and required_types:
        for rt in filter(lambda x: x not in ALLOWED_TYPES, required_types):
            raise ValueError(
                f"{rt} is in invalid type. Allowed types are {','.join(ALLOWED_TYPES)}"
            )

        if "ASCII_LOWER" in required_types:
            reqs.append("lowercase character")
            if not any(c in ascii_lowercase for c in value):
                if required_cnt is None:
                    errstr += "Must contain at least one lowercase character. "
            else:
                cnt += 1

        if "ASCII_UPPER" in required_types:
            reqs.append("uppercase character")
            if not any(c in ascii_uppercase for c in value):
                if required_cnt is None:
                    errstr += "Must contain at least one uppercase character. "
            else:
                cnt += 1

        if "DIGIT" in required_types:
            reqs.append("digits 0-9")
            if not any(c in digits for c in value):
                if required_cnt is None:
                    errstr += "Must contain at least one numeric digit (0-9). "
            else:
                cnt += 1

        if "SPECIAL" in required_types:
            reqs.append("special characters (!, $, #, %, etc.)")
            if not any(c in punctuation for c in value):
                if required_cnt is None:
                    errstr += "Must contain at least one special character (!, $, #, %, etc.). "
            else:
                cnt += 1

    if required_cnt and required_cnt > cnt:
        raise ValueError(
            f"Must contain at least {required_cnt} of the following categories: {', '.join(reqs)}"
        )

    if errstr:
        raise ValueError(errstr)
    return value


def passwd_complexity_validator(
    required_types: list[str] | None = None,
    required_cnt: int = 0,
    min_length: int = 8,
    max_length: int = 16,
) -> partial[str]:
    """Enforce password complexity.

    Args:
        required_types: list of strings or None.
            The allowed types are `ALLOWED_TYPES`.
        required_cnt: integer, The number of categories
            (in `ALLOWED_TYPES`) that the password must use.
        min_length: integer, The minimum length of the password.
        max_length: integer, The maximum length of the password.
    """
    return partial(
        __complexity_impl,
        required_types=required_types,
        required_cnt=required_cnt,
        min_length=min_length,
        max_length=max_length,
    )
