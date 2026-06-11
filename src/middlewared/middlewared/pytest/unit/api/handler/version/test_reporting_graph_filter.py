import pytest

from middlewared.api.base.handler.accept import validate_model
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter
from middlewared.api.v25_10_2.reporting import (
    ReportingNetdataGetDataArgs as ReportingNetdataGetDataArgs_v25_10_2,
)
from middlewared.api.v25_10_3.reporting import (
    ReportingNetdataGetDataArgs as ReportingNetdataGetDataArgs_v25_10_3,
)
from middlewared.api.v25_10_4.reporting import (
    ReportingNetdataGetDataArgs as ReportingNetdataGetDataArgs_v25_10_4,
)
from middlewared.api.v26_0_0.reporting import (
    ReportingNetdataGetDataArgs as ReportingNetdataGetDataArgs_v26_0_0,
)
from middlewared.service_exception import ValidationErrors

from .utils import TestModelProvider


def _build_adapter():
    return APIVersionsAdapter(
        [
            APIVersion(
                "v25.10.2",
                TestModelProvider(
                    {
                        "ReportingNetdataGetDataArgs": ReportingNetdataGetDataArgs_v25_10_2,
                    }
                ),
            ),
            APIVersion(
                "v25.10.3",
                TestModelProvider(
                    {
                        "ReportingNetdataGetDataArgs": ReportingNetdataGetDataArgs_v25_10_3,
                    }
                ),
            ),
            APIVersion(
                "v25.10.4",
                TestModelProvider(
                    {
                        "ReportingNetdataGetDataArgs": ReportingNetdataGetDataArgs_v25_10_4,
                    }
                ),
            ),
            APIVersion(
                "v26.0.0",
                TestModelProvider(
                    {
                        "ReportingNetdataGetDataArgs": ReportingNetdataGetDataArgs_v26_0_0,
                    }
                ),
            ),
        ]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("removed_name", ["arcrate", "arcactualrate", "arcresult"])
async def test_removed_graph_names_are_filtered_when_upgrading(removed_name):
    adapter = _build_adapter()
    value = {
        "graphs": [{"name": removed_name, "identifier": None}, {"name": "cpu", "identifier": None}],
        "query": {},
    }

    result = await adapter.adapt(value, "ReportingNetdataGetDataArgs", "v25.10.2", "v26.0.0")

    assert [g["name"] for g in result["graphs"]] == ["cpu"]


@pytest.mark.asyncio
async def test_all_removed_graphs_triggers_validation_error():
    adapter = _build_adapter()
    value = {
        "graphs": [{"name": "arcrate", "identifier": None}, {"name": "arcresult", "identifier": None}],
        "query": {},
    }

    adapted = await adapter.adapt(value, "ReportingNetdataGetDataArgs", "v25.10.2", "v26.0.0")
    assert adapted["graphs"] == []
    with pytest.raises(ValidationErrors):
        validate_model(ReportingNetdataGetDataArgs_v26_0_0, adapted)


@pytest.mark.asyncio
@pytest.mark.parametrize("removed_name", ["arcrate", "arcactualrate", "arcresult"])
async def test_current_v26_rejects_removed_names_directly(removed_name):
    with pytest.raises(ValidationErrors):
        validate_model(
            ReportingNetdataGetDataArgs_v26_0_0,
            {"graphs": [{"name": removed_name, "identifier": None}], "query": {}},
        )
