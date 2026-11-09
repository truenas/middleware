"""
This module holds the paths of truesearchd, the configuration file that middleware writes for it, and the control
sockets of both daemons. The README of the `configfile` crate in the truesearchd sources gives the format of the file.
The READMEs of the daemon and the indexer give the lines of the control sockets.
"""
from __future__ import annotations

from collections.abc import Iterable
import contextlib
from dataclasses import dataclass, replace
import hashlib
import os
import re
import socket
import time

# The system dataset child that holds the environments of the indexer. Middleware creates it.
TRUESEARCHD_DIR = '/var/db/system/truesearchd'
CONFIG_PATH = '/etc/truesearchd/truesearch.conf'
INDEXER_CONTROL = '/run/truesearchd/indexer'
DAEMON_CONTROL = '/run/truesearchd/control'

ID_MAX = 64
# The process names of the daemons. The kernel cuts them at 15 bytes.
DAEMON_NAMES = frozenset({'truesearchd', 'truesearch-inde'})
RELEASE_TIMEOUT = 10  # seconds
_ID_INVALID = re.compile(r'[^A-Za-z0-9_.-]')
_ROW_HEADER = re.compile(r'^\[target "([A-Za-z0-9_.-]+)"\]\s*$', re.MULTILINE)
_STATUS_HEADER = re.compile(
    r'^targets=\d+ draining=(?:true|false) index_bytes=(?P<index_bytes>\d+) free_bytes=(?P<free_bytes>\d+) '
    r'space_low=(?P<space_low>true|false)$'
)
# The keys come in this order. A root and an activity may hold spaces.
_STATUS_TARGET = re.compile(
    r'^target (?P<id>\S+) root=.*? live=(?P<live>\d+) tombstones=\d+ commit=\d+ '
    r'activity=(?P<activity>.*?) watching=(?P<watching>true|false) events=\d+ last_full=(?P<last_full>\d+) '
    r'last_dirs=(?P<last_dirs>\d+) map=\d+ queued=(?P<queued>\d+) size=(?P<size>\d+) ahead=\S+ fsid=\S+'
    r'(?: held=(?P<held>.*))?$'
)


@dataclass(frozen=True, slots=True)
class TargetRow:
    """
    One index target: the directory of one dataset that truesearchd indexes and serves. A disabled row is neither
    indexed nor served, and its index is kept.
    """
    id: str
    dataset: str
    root: str
    exclude: tuple[str, ...] = ()
    enabled: bool = True


def target_id(dataset: str, guid: str | None) -> str:
    """
    The label of a dataset's index target. A dataset keeps its GUID across a rename, so its index target keeps its
    id. Without a GUID the id comes from the name.
    """
    if guid:
        return f'ds{guid}'

    readable = _ID_INVALID.sub('_', dataset).lstrip('.') or 'ds'
    digest = hashlib.sha256(dataset.encode()).hexdigest()[:12]
    return f'{readable[:ID_MAX - len(digest) - 1]}-{digest}'


def quote(path: str) -> str:
    """A path in double quotes, escaped as the configuration file reads it."""
    out = ['"']
    for char in path:
        code = ord(char)
        if char == '\\':
            out.append('\\\\')
        elif char == '"':
            out.append('\\"')
        elif char == '\n':
            out.append('\\n')
        elif char == '\t':
            out.append('\\t')
        elif char == '\r':
            out.append('\\r')
        elif code < 0x20 or code == 0x7f:
            out.append(f'\\x{code:02x}')
        elif 0xdc80 <= code <= 0xdcff:
            # The surrogateescape error handler keeps a byte that is not UTF-8.
            out.append(f'\\x{code - 0xdc00:02x}')
        else:
            out.append(char)
    out.append('"')
    return ''.join(out)


def render_config(rows: list[TargetRow]) -> str:
    """The text of the configuration file: one `[target]` row for each index target, every path quoted."""
    lines = ['# Written by middleware. Changes here are lost.']
    for row in sorted(rows, key=lambda row: row.id):
        lines.append('')
        lines.append(f'# {row.dataset}')
        lines.append(f'[target "{row.id}"]')
        lines.append(f'root = {quote(row.root)}')
        if not row.enabled:
            lines.append('enabled = no')
        if row.exclude:
            lines.append(f'exclude = {", ".join(quote(path) for path in row.exclude)}')

    return '\n'.join(lines) + '\n'


_ESCAPES = {'\\': '\\', '"': '"', 'n': '\n', 't': '\t', 'r': '\r'}


def unquote(text: str) -> str | None:
    """A path as `quote` wrote it, read back. `None` when `text` is not one quoted path."""
    if len(text) < 2 or text[0] != '"' or text[-1] != '"':
        return None

    out = []
    i, body = 0, text[1:-1]
    while i < len(body):
        char = body[i]
        if char == '"':
            return None
        if char != '\\':
            out.append(char)
            i += 1
        elif (escape := body[i + 1:i + 2]) in _ESCAPES:
            out.append(_ESCAPES[escape])
            i += 2
        elif escape == 'x' and len(digits := body[i + 2:i + 4]) == 2 and _is_hex(digits):
            code = int(digits, 16)
            # A byte that is not UTF-8 returns as the surrogateescape error handler keeps it.
            out.append(chr(code) if code < 0x80 else chr(0xdc00 + code))
            i += 4
        else:
            return None

    return ''.join(out)


def rendered_rows(text: str) -> list[TargetRow]:
    """
    The rows of a configuration file middleware wrote. The dataset of a row is the comment above its header. A root
    that does not read back is empty. The exclusions are not read.
    """
    rows: list[TargetRow] = []
    comment = ''
    for line in text.splitlines():
        if (header := _ROW_HEADER.match(line)) is not None:
            rows.append(TargetRow(id=header[1], dataset=comment, root=''))
        elif rows and line.startswith('root = '):
            rows[-1] = replace(rows[-1], root=unquote(line.removeprefix('root = ')) or '')
        elif rows and line == 'enabled = no':
            rows[-1] = replace(rows[-1], enabled=False)
        comment = line.removeprefix('# ') if line.startswith('# ') else ''

    return rows


def beneath(path: str, top: str) -> bool:
    """Whether `path` is `top` or a path beneath it."""
    return path == top or path.startswith(top.rstrip('/') + '/')


def carried_rows(
    old: list[TargetRow], rows: list[TargetRow], imported: set[str], directories: set[str],
) -> list[TargetRow]:
    """
    The rows of the file `old` that stay, disabled, because their pool is not imported. A row stays while a share
    directory of `directories` is in its root or above it. So an exported pool keeps its index until its shares are
    deleted. A row of an imported pool is not carried, because its dataset is gone.
    """
    ids = {row.id for row in rows}
    roots = {row.root for row in rows}
    return [
        replace(row, enabled=False, exclude=())
        for row in old
        if row.root
        and row.dataset
        and row.dataset.split('/')[0] not in imported
        and row.id not in ids
        and row.root not in roots
        and any(beneath(row.root, directory) or beneath(directory, row.root) for directory in directories)
    ]


@dataclass(frozen=True, slots=True)
class IndexerTarget:
    """One index target in the indexer's status."""
    live: int
    activity: str
    watching: bool
    last_full: int
    last_dirs: int
    queued: int
    size: int
    held: str | None


@dataclass(frozen=True, slots=True)
class IndexerStatus:
    """The indexer's status: the space its indexes take, and each index target by id."""
    index_bytes: int
    free_bytes: int
    space_low: bool
    targets: dict[str, IndexerTarget]


def _is_hex(text: str) -> bool:
    return 0 < len(text) <= 6 and all(char in '0123456789abcdefABCDEF' for char in text)


def _unquote_debug(text: str) -> str:
    """A string as Rust's `{:?}` writes it, read back."""
    if len(text) < 2 or text[0] != '"' or text[-1] != '"':
        return text

    simple = {'n': '\n', 'r': '\r', 't': '\t', '0': '\0', '\\': '\\', '"': '"', "'": "'"}
    out = []
    i, body = 0, text[1:-1]
    while i < len(body):
        char = body[i]
        if char != '\\' or i + 1 == len(body):
            out.append(char)
            i += 1
        elif body[i + 1] in simple:
            out.append(simple[body[i + 1]])
            i += 2
        elif body[i + 1] == 'u' and (end := body.find('}', i)) != -1 and _is_hex(body[i + 3:end]):
            out.append(chr(int(body[i + 3:end], 16)))
            i = end + 1
        else:
            out.append(char)
            i += 1

    return ''.join(out)


def parse_indexer_status(text: str) -> IndexerStatus:
    """Parse the answer of the `status` request of the indexer. Raise `ValueError` if it is not a status."""
    lines = text.splitlines()
    if not lines or lines[0] != 'ok' or len(lines) < 2 or not (header := _STATUS_HEADER.match(lines[1])):
        raise ValueError(f'not a status: {text[:80]!r}')

    targets = {}
    for line in lines[2:]:
        if (match := _STATUS_TARGET.match(line)) is None:
            continue

        held = match['held']
        targets[match['id']] = IndexerTarget(
            live=int(match['live']),
            activity=match['activity'],
            watching=match['watching'] == 'true',
            last_full=int(match['last_full']),
            last_dirs=int(match['last_dirs']),
            queued=int(match['queued']),
            size=int(match['size']),
            held=None if held is None else _unquote_debug(held),
        )

    return IndexerStatus(
        index_bytes=int(header['index_bytes']),
        free_bytes=int(header['free_bytes']),
        space_low=header['space_low'] == 'true',
        targets=targets,
    )


def parse_served_ids(text: str) -> set[str]:
    """The ids of the index targets truesearchd serves, from the answer of its `status`."""
    lines = text.splitlines()
    if not lines or lines[0] != 'ok':
        raise ValueError(f'not a status: {text[:80]!r}')

    return {
        line.split(' ', 2)[1]
        for line in lines[1:]
        if line.startswith('target ') and ' served=false ' not in line
    }


def devices_of(paths: Iterable[str]) -> set[int]:
    """The devices of the filesystems that hold `paths`. A path that is gone is left out."""
    devices = set()
    for path in paths:
        with contextlib.suppress(OSError):
            devices.add(os.stat(path).st_dev)

    return devices


def daemons_holding(devices: set[int]) -> bool:
    """
    Whether truesearchd or truesearch-indexer has a file open on one of `devices`. Only the descriptors of the two
    daemons are examined, not those of every process.
    """
    for pid in os.listdir('/proc'):
        if not pid.isdigit():
            continue

        try:
            with open(f'/proc/{pid}/comm') as f:
                if f.read().rstrip('\n') not in DAEMON_NAMES:
                    continue

            for fd in os.listdir(f'/proc/{pid}/fd'):
                with contextlib.suppress(OSError):
                    if os.stat(f'/proc/{pid}/fd/{fd}').st_dev in devices:
                        return True
        except OSError:
            # The process exited during the check.
            continue

    return False


def wait_released(devices: set[int], timeout: float = RELEASE_TIMEOUT) -> bool:
    """
    Wait until neither daemon has a file open on `devices`. A reload answers before the daemons release the rows
    that it stopped. Return False if a daemon still holds a file after `timeout` seconds.
    """
    deadline = time.monotonic() + timeout
    while daemons_holding(devices):
        if time.monotonic() >= deadline:
            return False

        time.sleep(0.05)

    return True


def control_request(path: str, line: str, timeout: float = 120) -> str:
    """Send one line to a control socket and return its answer."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(path)
        sock.sendall(line.encode() + b'\n')
        sock.shutdown(socket.SHUT_WR)
        answer = bytearray()
        while chunk := sock.recv(4096):
            answer += chunk

    return answer.decode(errors='replace').strip()
