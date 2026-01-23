# -*- coding=utf-8 -*-
from collections.abc import Iterable
import shlex


def join_commandline(args: Iterable[str]) -> str:
    return " ".join(map(shlex.quote, args))
