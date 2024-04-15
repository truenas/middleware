# -*- coding=utf-8 -*-
import base64
import contextlib
import json
import textwrap

from .call import call
from .ssh import ssh

RESULT_PATH = "/tmp/mocked_binary_launch"


class BinaryMock:
    def _load(self):
        try:
            return json.loads(ssh(f"cat {RESULT_PATH}", check=False).strip())
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


def set_usr_readonly(value):
    cmd = 'python3 -c "import libzfs;'
    cmd += 'hdl = libzfs.ZFS().get_dataset_by_path(\\\"/usr\\\");'
    cmd += 'hdl.update_properties({\\\"readonly\\\": {\\\"value\\\": '
    cmd += f'\\\"{value}\\\"' + '}});"'
    ssh(cmd)


@contextlib.contextmanager
def mock_binary(path, code="", exitcode=1):
    set_usr_readonly("off")
    ssh(f"rm -f {RESULT_PATH}")
    ssh(f"mv {path} {path}.bak")
    try:
        call(
            "filesystem.file_receive",
            path,
            base64.b64encode(textwrap.dedent("""\
                #!/usr/bin/python3
                import json
                import sys
                
                exitcode = """ + repr(exitcode) + """
                result = {
                    "argv": sys.argv,
                }
                %code%
                with open(""" + repr(RESULT_PATH) + """, "w") as f:
                    json.dump(result, f)
                sys.exit(exitcode)
            """).replace("%code%", code).encode("utf-8")).decode("ascii"),
             {"mode": 0o755},
        )
        yield BinaryMock()
    finally:
        set_usr_readonly("off")  # In case something like `truenas-initrd.py` was launched by `yield`
        ssh(f"mv {path}.bak {path}")
        set_usr_readonly("on")
