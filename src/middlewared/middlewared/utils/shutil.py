# -*- coding=utf-8 -*-
import subprocess

__all__ = ["rmtree_one_filesystem"]


def rmtree_one_filesystem(path):
    subprocess.run(['rm', '--one-file-system', '-rf', path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                   encoding="utf-8", errors="ignore", check=True)
