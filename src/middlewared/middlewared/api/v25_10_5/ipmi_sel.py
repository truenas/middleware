from pydantic import Field

from middlewared.api.base import BaseModel


__all__ = ["IpmiSelElistEntry", "IpmiSelClearArgs", "IpmiSelClearResult", "IpmiSelInfoArgs", "IpmiSelInfoResult",]


class IpmiSelElistEntry(BaseModel):
    id: str = Field(description="Unique identifier for the SEL (System Event Log) entry.")
    date: str = Field(description="Date when the event occurred.")
    time: str = Field(description="Time when the event occurred.")
    name: str = Field(description="Name or description of the sensor that generated the event.")
    type: str = Field(description="Type of the event (e.g., \"Temperature\", \"Voltage\").")
    event_direction: str = Field(description="Direction of the event (e.g., \"Assertion\", \"Deassertion\").")
    event: str = Field(description="Detailed description of the event that occurred.")


class IPMISELInfo(BaseModel):
    sel_version: str = Field(description="Version of the SEL (System Event Log) implementation.")
    number_of_log_entries: str = Field(description="Total number of entries currently in the SEL.")
    free_space_remaining: str = Field(description="Amount of free space remaining in the SEL storage.")
    recent_erase_timestamp: str = Field(description="Timestamp of the most recent SEL erase operation.")
    get_sel_allocation_information_command: str = Field(
        description="Support status for the get SEL allocation information command.",
    )
    reserve_sel_command: str = Field(description="Support status for the reserve SEL command.")
    partial_add_sel_entry_command: str = Field(description="Support status for the partial add SEL entry command.")
    delete_sel_command: str = Field(description="Support status for the delete SEL command.")
    events_dropped_due_to_lack_of_space: str = Field(
        description="Number of events that were dropped due to insufficient SEL space.",
    )
    number_of_possible_allocation_units: str = Field(
        description="Total number of allocation units that can be used for SEL storage.",
    )
    allocation_unit_size: str = Field(description="Size of each allocation unit in bytes.")
    number_of_free_allocation_units: str = Field(description="Number of allocation units currently available for use.")
    largest_free_block: str = Field(description="Size of the largest contiguous free block in allocation units.")
    maximum_record_size: str = Field(description="Maximum size of a single SEL record in bytes.")


class IpmiSelClearArgs(BaseModel):
    pass


class IpmiSelClearResult(BaseModel):
    result: None = Field(description="Returns `null` when the SEL clear operation completes successfully.")


class IpmiSelInfoArgs(BaseModel):
    pass


class IpmiSelInfoResult(BaseModel):
    result: IPMISELInfo | dict = Field(description="SEL information or raw dictionary if parsing fails.")
