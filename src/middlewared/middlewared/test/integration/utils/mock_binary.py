# -*- coding=utf-8 -*-
import base64
import contextlib
import json
import textwrap

from .call import call
from .ssh import ssh


class BinaryMock:
    def _load(self):
        try:
            return json.loads(ssh("cat /tmp/mocked_binary_launch", check=False).strip())
        except ValueError:
            return None

    @property
    def launched(self):
        return self._load() is not None

    @property
    def result(self):
        result = self._load()
        if result is None:
            raise AttributeError("mocked binary was not launched")

        return result


@contextlib.contextmanager
def mock_binary(path, code="", exitcode=1):
    ssh("rm -f /tmp/mocked_binary_launch")
    ssh(f"mv {path} {path}.bak")
    try:
        call(
            "filesystem.file_receive",
            path,
            base64.b64encode(textwrap.dedent("""\
                #!/usr/bin/python3
                import json
                import sys
                
                exitcode = %exitcode%
                result = {
                    "argv": sys.argv,
                }
                %code%
                with open("/tmp/mocked_binary_launch", "w") as f:
                    json.dump(result, f)
                sys.exit(exitcode)
            """).replace("%exitcode%", str(exitcode)).replace("%code%", code).encode("utf-8")).decode("ascii"),
             {"mode": 0o755},
        )
        yield BinaryMock()
    finally:
        ssh(f"mv {path}.bak {path}")
