from contextlib import suppress
import errno
import os
from typing import Any, Literal

from truenas_os_pyutils.io import atomic_write

from middlewared.api.base import BaseModel
from middlewared.api.current import NFSGetNfs3ClientsEntry, NFSGetNfs4ClientsEntry
from middlewared.service_exception import CallError
from middlewared.utils.yaml import safe_yaml_load

from .utils import NFSServicePathInfo

ThreadpoolMode = Literal["AUTO", "GLOBAL", "PERCPU", "PERNODE"]

NFS4_CLIENTS_DIR = "/proc/fs/nfsd/clients"
POOL_MODE_PATH = "/sys/module/sunrpc/parameters/pool_mode"


class NFSGetRmtabArgs(BaseModel):
    pass


class NFSGetRmtabResult(BaseModel):
    result: list[NFSGetNfs3ClientsEntry]


class NFSClearNfs3RmtabArgs(BaseModel):
    ip_to_clear: list[str] | None = None


class NFSClearNfs3RmtabResult(BaseModel):
    result: None


class NFSGetNfs4ClientInfoArgs(BaseModel):
    id_: str


class NFSGetNfs4ClientInfoResult(BaseModel):
    result: dict[str, Any]


class NFSGetNfs4ClientStatesArgs(BaseModel):
    id_: str


class NFSGetNfs4ClientStatesResult(BaseModel):
    result: list[Any]


class NFSCloseClientStateArgs(BaseModel):
    client_id: str


class NFSCloseClientStateResult(BaseModel):
    result: None


class NFSGetThreadpoolModeArgs(BaseModel):
    pass


class NFSGetThreadpoolModeResult(BaseModel):
    result: ThreadpoolMode


class NFSSetThreadpoolModeArgs(BaseModel):
    pool_mode: ThreadpoolMode


class NFSSetThreadpoolModeResult(BaseModel):
    result: None


def _rmtab_path() -> str:
    return os.path.join(NFSServicePathInfo.STATEDIR.path, "rmtab")


def get_rmtab() -> list[NFSGetNfs3ClientsEntry]:
    """
    In future we can apply enhance based on socket status
    e.g ss -H -o state established '( sport = :nfs )'
    """
    entries = []
    with suppress(FileNotFoundError):
        with open(_rmtab_path(), "r") as f:
            for line in f:
                ip, data = line.split(":", 1)
                export, refcnt = line.rsplit(":", 1)
                # for now we won't display the refcnt
                entries.append(NFSGetNfs3ClientsEntry(ip=ip, export=export))

    return entries


def clear_nfs3_rmtab(ip_to_clear: list[str] | None = None) -> None:
    """
    Clear some or all NFSv3 client entries in rmtab.
    rmtab can become clogged with stale entries, this provides a
    method to clear all or selected entries.
    Optional input: list of ip to remove, e.g. ip_to_clear=["a.b.c.d"]
    DEFAULT: Clear all entries
    """
    if ip_to_clear is None:
        ip_to_clear = ["all"]

    rmtab = _rmtab_path()
    with suppress(FileNotFoundError):
        if "all" in ip_to_clear:
            with open(rmtab, "w"):
                # Use 'w' open to truncate
                pass
        else:
            # Replace rmtab excluding ip_to_clear
            with atomic_write(rmtab) as outf:
                with open(rmtab, "r") as inf:
                    for entry in inf:
                        if entry.split(":")[0] in ip_to_clear:
                            continue
                        else:
                            outf.write(entry)


def get_nfs4_client_info(id_: str) -> dict[str, Any]:
    """
    See the following link:
        NFS 4.1 spec: https://www.rfc-editor.org/rfc/rfc8881.html
    """
    info: dict[str, Any] = {}
    with suppress(FileNotFoundError):
        with open(os.path.join(NFS4_CLIENTS_DIR, id_, "info"), "r") as f:
            info = safe_yaml_load(f)

            # NFS-135435: Fixup non-printable chars
            for item in ["name", "Implementation domain", "Implementation name"]:
                if raw_val := info.get(item):
                    info[item] = "".join(c if c.isprintable() else "\ufffd" for c in raw_val)

    return info


def get_nfs4_client_states(id_: str) -> list[Any]:
    """
    Detailed information regarding current open files per NFS client
    TODO: review formatting of this field
    """
    states = []
    with suppress(FileNotFoundError):
        with open(os.path.join(NFS4_CLIENTS_DIR, id_, "states"), "r") as f:
            states = safe_yaml_load(f)

    # states file may be empty, which changes it to None type
    # return empty list in this case
    return states or []


def get_nfs4_clients() -> list[NFSGetNfs4ClientsEntry]:
    clients = []
    with suppress(FileNotFoundError):
        for client in os.listdir(NFS4_CLIENTS_DIR):
            clients.append(
                NFSGetNfs4ClientsEntry(
                    id=client,
                    info=get_nfs4_client_info(client),
                    states=get_nfs4_client_states(client),
                )
            )

    return clients


def close_client_state(client_id: str) -> None:
    """
    force the server to immediately revoke all state held by:
    `client_id`. This only applies to NFSv4. `client_id` is `id`
    returned in `get_nfs4_clients`.
    """
    with suppress(FileNotFoundError):
        with open(os.path.join(NFS4_CLIENTS_DIR, client_id, "ctl"), "w") as f:
            f.write("expire\n")


def get_threadpool_mode() -> ThreadpoolMode:
    with open(POOL_MODE_PATH, "r") as f:
        pool_mode = f.readline().strip()

    return pool_mode.upper()  # type: ignore[return-value]


def set_threadpool_mode(pool_mode: ThreadpoolMode) -> None:
    """
    Control how the NFS server code allocates CPUs to
    service thread pools.  Depending on how many NICs
    you have and where their interrupts are bound, this
    option will affect which CPUs will do NFS serving.
    Note: this parameter cannot be changed while the
    NFS server is running.

    auto        the server chooses an appropriate mode
                automatically using heuristics
    global      a single global pool contains all CPUs
    percpu      one pool for each CPU
    pernode     one pool for each NUMA node (equivalent
                to global on non-NUMA machines)
    """
    try:
        with open(POOL_MODE_PATH, "w") as f:
            f.write(pool_mode.lower())
    except OSError as e:
        raise CallError("NFS service must be stopped before threadpool mode changes", errno=e.errno or errno.EFAULT)
