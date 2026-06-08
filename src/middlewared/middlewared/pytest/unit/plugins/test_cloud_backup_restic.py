# flake8: noqa
import io
import json
from unittest.mock import MagicMock

from middlewared.plugins.cloud_backup.restic import restic_check_progress


class FakeStdout:
    """Minimal stand-in for `proc.stdout`: yields the given byte lines, then EOF."""

    def __init__(self, lines):
        self._lines = list(lines)

    def readline(self):
        if self._lines:
            return self._lines.pop(0)
        return b""

    def read(self):
        data = b"".join(self._lines)
        self._lines = []
        return data


def make_proc(lines):
    proc = MagicMock()
    proc.stdout = FakeStdout(lines)
    return proc


def make_job():
    job = MagicMock()
    job.internal_data = {}
    job.logs_fd = io.BytesIO()
    return job


def line(obj):
    return (json.dumps(obj) + "\n").encode("utf-8")


def test_error_message_is_decoded_from_nested_object():
    # restic nests the text as {"error": {"message": "..."}}. This is the exact
    # shape that previously crashed with KeyError: 'error.message'.
    job = make_job()
    restic_check_progress(
        job,
        make_proc([line({
            "message_type": "error",
            "error": {"message": "repository is already locked"},
            "during": "archival",
            "item": "/mnt/tank/data",
        })]),
        track_progress=True,
    )

    assert job.internal_data["messages"] == [
        "Error in /mnt/tank/data while archival: repository is already locked"
    ]
    # The nested access succeeded, so the broad guard must NOT have fired.
    job.middleware.logger.warning.assert_not_called()


def test_malformed_error_does_not_kill_reader_and_logs_once():
    # An unexpected message shape (e.g. restic's pre-0.17.1 empty `{}`) must not
    # raise out of the reader thread (which would stop draining stdout and hang
    # the job). It is recorded and the traceback is logged at most once per run.
    job = make_job()
    bad = line({"message_type": "error", "error": {}, "during": "archival", "item": "/x"})
    restic_check_progress(job, make_proc([bad, bad]), track_progress=True)

    # Both malformed lines recorded, but only one system-log traceback emitted.
    assert job.internal_data["messages"] == [bad.decode(), bad.decode()]
    job.middleware.logger.warning.assert_called_once()


def test_status_message_updates_progress():
    job = make_job()
    restic_check_progress(
        job,
        make_proc([line({"message_type": "status", "percent_done": 0.5})]),
        track_progress=True,
    )

    job.set_progress.assert_called()
    assert job.set_progress.call_args.args[0] == 50.0
    job.middleware.logger.warning.assert_not_called()
