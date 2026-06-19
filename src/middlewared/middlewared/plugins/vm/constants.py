import enum


class VMGuestArch(enum.StrEnum):
    X86_64 = "x86_64"
    AARCH64 = "aarch64"
    I686 = "i686"
