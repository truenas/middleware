# -*- coding=utf-8 -*-
import shlex


def join_commandline(args):
    return " ".join(map(shlex.quote, args))
