from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, single_argument_result
from .common import CronModel, QueryFilters, QueryOptions
from .smartctl import AtaSelfTest, NvmeSelfTest, ScsiSelfTest

__all__ = ["SmartTestEntry",
           "SmartTestCreateArgs", "SmartTestCreateResult",
           "SmartTestUpdateArgs", "SmartTestUpdateResult",
           "SmartTestDeleteArgs", "SmartTestDeleteResult",
           "SmartTestQueryForDiskArgs", "SmartTestQueryForDiskResult",
           "SmartTestDiskChoicesArgs", "SmartTestDiskChoicesResult",
           "SmartTestManualTestArgs", "SmartTestManualTestResult",
           "SmartTestResultsArgs", "SmartTestResultsResult",
           "SmartTestAbortArgs", "SmartTestAbortResult"]


class SmartTestCron(CronModel):
    minute: Excluded = excluded_field()


class SmartTestEntry(BaseModel):
    id: int
    schedule: SmartTestCron
    desc: str
    all_disks: bool = False
    "when enabled sets the task to cover all disks in which case `disks` is not required."
    disks: list[str] = Field(default_factory=list)
    "a list of valid disks which should be monitored in this task."
    type: Literal["LONG", "SHORT", "CONVEYANCE", "OFFLINE"]
    "the type of SMART test to be executed."


class SmartTestCreate(SmartTestEntry):
    id: Excluded = excluded_field()


class SmartTestCreateArgs(BaseModel):
    smart_task_create: SmartTestCreate


class SmartTestCreateResult(BaseModel):
    result: SmartTestEntry


class SmartTestUpdate(SmartTestCreate, metaclass=ForUpdateMetaclass):
    pass


class SmartTestUpdateArgs(BaseModel):
    id: int
    smart_task_update: SmartTestUpdate


class SmartTestUpdateResult(BaseModel):
    result: SmartTestEntry


class SmartTestDeleteArgs(BaseModel):
    id: int


class SmartTestDeleteResult(BaseModel):
    result: Literal[True]


class SmartTestQueryForDiskArgs(BaseModel):
    disk: str


class SmartTestQueryForDiskResult(BaseModel):
    result: list[SmartTestEntry]


class SmartTestDiskChoicesArgs(BaseModel):
    full_disk: bool = False


class SmartTestDiskChoicesResult(BaseModel):
    result: dict[str, str] | dict[str, dict]


class ManualTestParams(BaseModel):
    identifier: str
    mode: Literal["FOREGROUND", "BACKGROUND"] = "BACKGROUND"
    type: Literal["LONG", "SHORT", "CONVEYANCE", "OFFLINE"]
    "what type of SMART test will be ran"


class ManualTestResult(BaseModel):
    disk: str
    identifier: str
    error: str | None
    expected_result_time: datetime | None
    job: int | None


class SmartTestManualTestArgs(BaseModel):
    disks: list[ManualTestParams]


class SmartTestManualTestResult(BaseModel):
    result: list[ManualTestResult]


class SmartTestResultsArgs(BaseModel):
    filters: QueryFilters = Field(default_factory=list)
    options: QueryOptions = Field(default_factory=QueryOptions)
    "`extra.tests_filter` is an optional filter for tests results."


class CurrentTest(BaseModel):
    progress: int


class DiskTestResults(BaseModel):
    # Instead of `extra="ignore"`, just inherit this from `Disk`
    model_config = ConfigDict(
        strict=True,
        str_max_length=1024,
        use_attribute_docstrings=True,
        extra="ignore",
    )

    disk: str
    tests: list[AtaSelfTest] | list[NvmeSelfTest] | list[ScsiSelfTest]
    current_test: CurrentTest | None


class SmartTestResultsResult(BaseModel):
    result: list[DiskTestResults]


class SmartTestAbortArgs(BaseModel):
    disk: str


class SmartTestAbortResult(BaseModel):
    result: None
