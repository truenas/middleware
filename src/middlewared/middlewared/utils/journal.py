import datetime
import json
import subprocess
import time

__all__ = (
    "format_journal_record",
    "monotonic_to_realtime_since",
    "query_journal",
)


def query_journal(match_args: list[str], since: str | None = None) -> list[dict]:
    """
    Query journalctl and return parsed JSON records.

    Args:
        match_args: List of match arguments for journalctl
        since: Optional --since timestamp string (e.g., "2024-01-15 10:30:00")

    Returns:
        List of parsed journal record dictionaries
    """
    cmd = ["journalctl", "--no-pager", "--output=json"]

    if since:
        cmd.extend(["--since", since])

    cmd.extend(match_args)

    result = subprocess.run(cmd, capture_output=True, text=True)

    records = []
    if result.returncode != 0:
        return records

    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return records


def format_journal_record(record: dict) -> str:
    """Format a journal record as a log line."""
    ts = datetime.datetime.fromtimestamp(
        int(record.get("__REALTIME_TIMESTAMP", 0)) / 1_000_000
    )
    syslog_id = record.get("SYSLOG_IDENTIFIER", "")
    pid = record.get("_PID", "0")
    message = record.get("MESSAGE", "")
    return f"{ts.strftime('%b %d %H:%M:%S')} {syslog_id}[{pid}]: {message}"


def monotonic_to_realtime_since(monotonic_us: int) -> str:
    """Convert monotonic timestamp (microseconds) to --since string for journalctl."""
    # We use CLOCK_MONOTONIC because journalctl's monotonic timestamps
    # exclude sleep time, just like this clock.
    uptime_ns = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    current_time_ns = time.time_ns()
    boot_time = (current_time_ns - uptime_ns) / 1e9
    realtime_ts = boot_time + (monotonic_us / 1_000_000)
    return datetime.datetime.fromtimestamp(realtime_ts).strftime("%Y-%m-%d %H:%M:%S")
