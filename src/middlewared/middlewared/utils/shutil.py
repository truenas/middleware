# -*- coding=utf-8 -*-
import subprocess

__all__ = ["rmtree_one_filesystem"]


def rmtree_one_filesystem(path: str) -> None:
    try:
        subprocess.run(['rm', '--one-file-system', '-rf', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       encoding="utf-8", errors="ignore", check=True)
    except subprocess.CalledProcessError as e:
        raise OSError(e.stderr.rstrip())
