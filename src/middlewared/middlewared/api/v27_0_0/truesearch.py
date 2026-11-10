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

# The filters that `middlewared.utils.truesearch_filters` converts into a Spotlight query.
_QUERY_FILTERS_DOC = (
    "The filters that select the files and directories. Write each filter as `[field, operator, value]`, as in other "
    'query methods. All filters must match. To match one of several filters, use `["OR", [filter, filter]]`. If you '
    "give no filters, the query returns all files and directories in `path` and its subdirectories.\n"
    "\n"
    "TrueSearch uses the index that answers macOS Spotlight searches through SMB. Middleware converts the filters "
    "into a Spotlight query. Thus, a query gets the same results as a Spotlight search from a Mac. TrueSearch does "
    "not use regular expressions.\n"
    "\n"
    "Text fields:\n"
    "\n"
    "* `name`: The name of the file or directory.\n"
    "* `comment`: The comment that a macOS user set on the file in the Finder.\n"
    "\n"
    "Text fields use these operators:\n"
    "\n"
    "* `=` and `!=` compare the full value.\n"
    "* `^` and `!^` compare the start of the value.\n"
    "* `$` and `!$` compare the end of the value.\n"
    "* `rin` finds the text anywhere in the value. `rnin` finds values that do not contain the text.\n"
    "* `in` and `nin` compare the full value with each value in a list.\n"
    "* Put `C` before an operator to ignore case and accents, for example `C=` or `Crin`.\n"
    "\n"
    "Tag fields:\n"
    "\n"
    "* `tags`: The tags that a macOS user set on the file in the Finder.\n"
    "\n"
    "Tag fields use these operators:\n"
    "\n"
    "* `rin` finds files that have the tag. `rnin` finds files that do not have the tag.\n"
    "* The tag must agree with the full value. Put `C` before the operator to ignore case and accents.\n"
    "\n"
    "Number fields:\n"
    "\n"
    "* `size`: The size in bytes. For a directory, ZFS gives the number of entries in the directory.\n"
    "* `uid`: The user ID of the owner.\n"
    "* `gid`: The group ID of the owner group.\n"
    "\n"
    "Number fields use these operators:\n"
    "\n"
    "* `=`, `!=`, `>`, `>=`, `<`, and `<=` compare the value.\n"
    "* `in` and `nin` compare the value with each value in a list.\n"
    "\n"
    "Date fields:\n"
    "\n"
    "* `mtime`: The last time that the data changed.\n"
    "* `btime`: The time that the file was created.\n"
    "* `atime`: The last time that the file was read.\n"
    "\n"
    "Date fields use these operators:\n"
    "\n"
    "* `=`, `!=`, `>`, `>=`, `<`, and `<=` compare the date.\n"
    "* Write the date as an ISO-8601 string, for example `2026-01-31T09:00:00`. A date without a time zone is in "
    "UTC. As in other query methods, you can add `.$date` to the field name.\n"
    "\n"
    "Choice fields:\n"
    "\n"
    "* `type`: The type of the entry.\n"
    "  * `DIRECTORY`: A directory. A macOS package is also a directory.\n"
    "  * `FILE`: A file. FIFOs, sockets, and device files are also files here.\n"
    "  * `SYMLINK`: A symbolic link. TrueSearch does not follow links.\n"
    "* `macos_kind`: The kind of file that the macOS Finder shows. TrueSearch gets the kind from the file name "
    "extension, not from the content. A file with an unknown extension has no kind.\n"
    "  * `FOLDER`: A directory that is not a macOS package.\n"
    "  * `PDF`: A PDF document with the `.pdf` extension.\n"
    "  * `IMAGE`: An image, for example `.jpg`, `.png`, `.gif`, `.heic`, `.tiff`, or `.psd`.\n"
    "  * `MOVIE`: A video, for example `.mp4`, `.mov`, `.mkv`, or `.avi`.\n"
    "  * `AUDIO`: An audio file, for example `.mp3`, `.m4a`, `.flac`, or `.wav`.\n"
    "  * `TEXT`: A text file, for example `.txt`, `.md`, `.csv`, `.html`, or source code.\n"
    "  * `DOCUMENT`: A word processor document: `.doc`, `.docx`, `.odt`, `.rtf`, or `.pages`.\n"
    "  * `SPREADSHEET`: A spreadsheet: `.xls`, `.xlsx`, `.ods`, `.numbers`, or `.csv`.\n"
    "  * `PRESENTATION`: A presentation: `.ppt`, `.pptx`, `.odp`, or `.key`.\n"
    "  * `ARCHIVE`: An archive: `.zip`, `.7z`, `.rar`, `.tar`, `.gz`, or `.xz`.\n"
    "  * `APPLICATION`: A macOS application with the `.app` extension, or a disk image. A Windows program with the "
    "`.exe` extension is not an application here.\n"
    "  * `DISK_IMAGE`: A disk image: a `.dmg` file, or a `.sparsebundle` or `.backupbundle` package.\n"
    "  * `PACKAGE`: A macOS package. A package is a directory that a Mac shows as one item, for example `.app`, "
    "`.sparsebundle`, `.photoslibrary`, or `.rtfd`.\n"
    "  * `FONT`: A font: `.ttf`, `.otf`, `.woff`, or `.woff2`.\n"
    "  * `CONTACT`: A contact card with the `.vcf` extension.\n"
    "  * `MAIL`: An email message with the `.eml` extension.\n"
    "\n"
    "Choice fields use these operators:\n"
    "\n"
    "* `=` and `!=` compare the value.\n"
    "* `in` and `nin` compare the value with each value in a list.\n"
    "\n"
    "Examples:\n"
    "\n"
    '* `[["name", "Crin", "report"]]` finds names that contain "report", in any case.\n'
    '* `[["macos_kind", "=", "PDF"], ["size", ">", 1048576]]` finds PDF documents that are larger than 1 MiB.\n'
    '* `[["OR", [["name", "$", ".jpg"], ["name", "$", ".png"]]]]` finds names that end with `.jpg` or `.png`.\n'
    '* `[["mtime", ">=", "2026-01-01T00:00:00"]]` finds files that changed in 2026 or later.\n'
    '* `[["tags", "rin", "Important"]]` finds files that have the tag "Important".'
)


class TruesearchQueryOptions(BaseModel):
    """
    Options for the results of the query.

    A query finds at most 1000 entries.
    TrueSearch returns the newest entries first and cannot sort them in a different order.
    Thus, `order_by`, `offset`, `count` and the other options of other query methods are not available.
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
        description="The user to search as. The results include only the files and directories that this user can "
        "access. An administrator can use this to see what the user can find. If `username` is `null`, "
        "the search runs as root and returns all matches.",
    )
    recursive: bool = Field(
        default=False,
        description="Also search the indexed datasets that are mounted beneath `path`. Each dataset has a separate "
        "index. Without `recursive`, the query searches only the dataset that contains `path`. With "
        "`recursive`, the query merges the results of all datasets, newest first. `limit` applies to the "
        "merged results.",
    )
    query_filters: QueryFilters = Field(alias="query-filters", default=[], description=_QUERY_FILTERS_DOC)
    query_options: TruesearchQueryOptions = Field(
        alias="query-options",
        default=TruesearchQueryOptions(),
        description="Options for the results of the query. They are not the options of other query methods.",
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
        description="The file handle of the file, encoded in base64. It is a `struct file_handle` of ZFS: the size "
        "and the type of the handle as 32-bit integers in host byte order, then the 12 bytes of the handle. Use it "
        "with `open_by_handle_at`.",
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
