# -*- coding=utf-8 -*-
import contextlib
import textwrap

from .mock_binary import mock_binary


@contextlib.contextmanager
def mock_rclone():
    with mock_binary(
        "/usr/bin/rclone",
        textwrap.dedent("""\
            import configparser
            config = configparser.ConfigParser()
            config.read(sys.argv[sys.argv.index("--config") + 1])
            result["config"] = {s: dict(config.items(s)) for s in config.sections()}
        """),
    ) as mb:
        yield mb
