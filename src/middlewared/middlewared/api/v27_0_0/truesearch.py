from datetime import datetime
from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString

from .common import QueryFilters
from .filesystem import FileType

__all__ = [
    "TruesearchQuery",
    "TruesearchQueryOptions",
    "TruesearchQueryArgs",
    "TruesearchEntry",
    "TruesearchEntryType",
    "TruesearchQueryResult",
    "TruesearchState",
    "TruesearchDatasetStatus",
    "TruesearchStatusData",
    "TruesearchStatusArgs",
    "TruesearchStatusResult",
]


class TruesearchQueryOptions(BaseModel):
    """
    Options for the results of the query.

    A query finds at most 1000 entries.
    TrueSearch returns the newest entries first.
    """

    # The limit is RIX_MAX_RESULTS of truesearchd.
    limit: int = Field(default=100, ge=1, le=1000, description="The maximum number of entries to return.")


class TruesearchQuery(BaseModel):
    path: NonEmptyString = Field(
        description="The directory to search. Use an absolute path in a dataset that TrueSearch indexes. TrueSearch "
        "indexes each dataset that contains an SMB share with Spotlight search enabled, or a WebShare "
        "share with search enabled. If `path` is above the indexed directory of the dataset, TrueSearch "
        "searches all of the indexed directory.",
    )
    username: str | None = Field(
        default=None,
        description="The user to search as. The user must be able to access `path`. The results include only the "
        "files and directories that this user can access. An administrator can use this to see what the user can "
        "find. If `username` is `null`, the search runs as root and returns all matches.",
    )
    recursive: bool = Field(
        default=False,
        description="Also search the indexed datasets that are mounted beneath `path`. Each dataset has a separate "
        "index. Without `recursive`, the query searches only the dataset that contains `path`. With "
        "`recursive`, the query merges the results of all datasets, newest first. `limit` applies to the "
        "merged results.",
    )
    query_filters: QueryFilters = Field(
        alias="query-filters",
        default=[],
        description="Filters can also use `macos_kind`, `tags`, and `comment`. These fields are not in the results.",
    )
    query_options: TruesearchQueryOptions = Field(
        alias="query-options",
        default=TruesearchQueryOptions(),
        description="Options for the results of the query.",
    )


class TruesearchQueryArgs(BaseModel):
    data: TruesearchQuery = Field(description="The directory to search, the filters, the options, and the user.")


TruesearchEntryType = FileType


class TruesearchEntry(BaseModel):
    path: str = Field(description="The absolute path of the file or directory.")
    name: str = Field(description="The name of the file or directory.")
    type: TruesearchEntryType = Field(
        description="The type of the file or directory. `OTHER` is a FIFO, a socket, or a device file.",
    )
    size: int | None = Field(description="The size in bytes.")
    mode: int | None = Field(description="The file mode, as `st_mode` gives it.")
    uid: int | None = Field(description="The user ID of the owner.")
    gid: int | None = Field(description="The group ID of the owner group.")
    mtime: datetime | None = Field(description="The last time that the data changed.")
    btime: datetime | None = Field(description="The time that the file was created.")
    atime: datetime | None = Field(description="The last time that the file was read.")
    inode: int | None = Field(description="The inode number, as `st_ino` gives it.")
    handle: str | None = Field(
        description="A file handle, encoded in base64. Use it on the NAS to open the file in a race-free manner. It "
        "identifies the file uniquely in its dataset for the lifetime of the file.",
    )


class TruesearchQueryResult(BaseModel):
    result: list[TruesearchEntry] = Field(description="The entries that match, with the newest entries first.")


TruesearchState = Literal["READY", "INDEXING", "UNAVAILABLE", "STOPPED"]


class TruesearchDatasetStatus(BaseModel):
    dataset: str = Field(description="The name of the ZFS dataset.")
    path: str = Field(
        description="The directory that TrueSearch indexes in the dataset. It is the deepest directory that contains "
        "all of the indexed shares in the dataset.",
    )
    state: TruesearchState = Field(
        description="The state of the index of this dataset:\n\n"
        "* `READY`: The index is up to date.\n"
        "* `INDEXING`: The indexer builds or updates the index. During the first build, a search finds "
        "nothing in this dataset.\n"
        "* `UNAVAILABLE`: TrueSearch does not index or search the dataset now. `reason` gives the reason.\n"
        "* `STOPPED`: The indexer does not run.",
    )
    reason: str | None = Field(
        description="The reason that the dataset is unavailable. This is `null` for the other states.",
    )
    served: bool = Field(description="Whether searches use this index.")
    entries: int | None = Field(description="The number of files and directories in the index.")
    watching: bool | None = Field(description="Whether the indexer adds changes when they occur.")
    last_full_pass: datetime | None = Field(description="The time that the last pass over all files ended.")
    last_directory_pass: datetime | None = Field(
        description="The time that the last pass over all directories ended.",
    )
    index_size: int | None = Field(description="The size of the index of this dataset, in bytes.")


class TruesearchStatusData(BaseModel):
    running: bool = Field(description="Whether the indexer responds.")
    index_bytes: int | None = Field(
        description="The size of all indexes, in bytes. The indexes are in the index dataset. It is the dataset "
        "`.system/truesearchd` on the pool of the system dataset. Its mountpoint is `/var/db/system/truesearchd`.",
    )
    free_bytes: int | None = Field(description="The free space in the index dataset, in bytes.")
    space_low: bool | None = Field(
        description="Whether the free space in the index dataset is less than twice the size of the largest index, or "
        "less than a rebuild of that index needs.",
    )
    datasets: list[TruesearchDatasetStatus] = Field(description="The status of each dataset that TrueSearch indexes.")


class TruesearchStatusArgs(BaseModel):
    pass


class TruesearchStatusResult(BaseModel):
    result: TruesearchStatusData = Field(description="The indexing status of TrueSearch.")
