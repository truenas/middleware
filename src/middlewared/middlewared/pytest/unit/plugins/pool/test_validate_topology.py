import pytest
from unittest.mock import Mock

from middlewared.plugins.pool_.pool import PoolService
from middlewared.pytest.unit.middleware import Middleware


def _new_vdev(vdev_type, num_disks):
    """A vdev spec as it arrives in data['topology'] on create/update."""
    return {'type': vdev_type, 'disks': [f'sd{i}' for i in range(num_disks)]}


def _existing_vdev(vdev_type, num_disks):
    """An existing vdev in a pool's stored topology (disk_to_stripe form)."""
    return {'type': vdev_type, 'children': [{'type': 'DISK'} for _ in range(num_disks)]}


def _pool_data(data, *, special=None, dedup=None, force_topology=False):
    return {
        'topology': {'data': data, 'special': special or [], 'dedup': dedup or []},
        'force_topology': force_topology,
    }


def _pool_old(data, *, special=None, dedup=None):
    return {'topology': {'data': data, 'special': special or [], 'dedup': dedup or []}}


def _service(is_enterprise=False):
    middleware = Middleware()
    middleware['system.is_enterprise'] = Mock(return_value=is_enterprise)
    return PoolService(middleware)


# ---------------------------------------------------------------------------
# Valid topologies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uniform_raidz2_is_valid():
    verrors = await _service()._validate_topology(
        _pool_data([_new_vdev('RAIDZ2', 7), _new_vdev('RAIDZ2', 7)])
    )
    assert verrors.errors == []


@pytest.mark.asyncio
async def test_stripe_width_is_not_capped():
    # STRIPE has no geometry to match and no maximum width.
    verrors = await _service()._validate_topology(_pool_data([_new_vdev('STRIPE', 20)]))
    assert verrors.errors == []


@pytest.mark.asyncio
async def test_extend_matching_width_is_valid():
    verrors = await _service()._validate_topology(
        _pool_data([_new_vdev('RAIDZ2', 7)]),
        _pool_old([_existing_vdev('RAIDZ2', 7)]),
    )
    assert verrors.errors == []


# ---------------------------------------------------------------------------
# Width consistency (data vdevs must be the same width)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mismatched_data_width_rejected_on_create():
    # Both within the width cap, so only the consistency check fires.
    verrors = await _service()._validate_topology(
        _pool_data([_new_vdev('RAIDZ2', 7), _new_vdev('RAIDZ2', 10)])
    )
    assert [e.attribute for e in verrors.errors] == ['topology.data.1.disks']
    assert 'different widths' in verrors.errors[0].errmsg


@pytest.mark.asyncio
async def test_mismatched_data_width_rejected_on_extend():
    verrors = await _service()._validate_topology(
        _pool_data([_new_vdev('RAIDZ2', 10)]),
        _pool_old([_existing_vdev('RAIDZ2', 7)]),
    )
    assert any('different widths' in e.errmsg for e in verrors.errors)


# ---------------------------------------------------------------------------
# Maximum width cap (RAIDZ 15, mirror 4); dRAID/STRIPE exempt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raidz_width_cap_rejected():
    verrors = await _service()._validate_topology(_pool_data([_new_vdev('RAIDZ2', 16)]))
    assert [e.attribute for e in verrors.errors] == ['topology.data.0.disks']
    assert verrors.errors[0].errmsg == 'You can have at most 15 disk(s) for this vdev type.'


@pytest.mark.asyncio
async def test_mirror_width_cap_rejected():
    verrors = await _service()._validate_topology(_pool_data([_new_vdev('MIRROR', 5)]))
    assert verrors.errors[0].errmsg == 'You can have at most 4 disk(s) for this vdev type.'


@pytest.mark.asyncio
async def test_max_width_only_applies_to_new_vdevs_on_extend():
    # An over-wide existing vdev is not re-flagged; the matching new vdev passes.
    verrors = await _service()._validate_topology(
        _pool_data([_new_vdev('RAIDZ2', 16)]),
        _pool_old([_existing_vdev('RAIDZ2', 16)]),
    )
    assert [e.attribute for e in verrors.errors] == ['topology.data.0.disks']
    assert verrors.errors[0].errmsg == 'You can have at most 15 disk(s) for this vdev type.'


# ---------------------------------------------------------------------------
# Pre-existing checks that force_topology also bypasses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mixed_data_types_rejected():
    verrors = await _service()._validate_topology(
        _pool_data([_new_vdev('RAIDZ2', 7), _new_vdev('MIRROR', 2)])
    )
    assert any(
        e.attribute == 'topology.data.1.type' and 'different data vdev types' in e.errmsg
        for e in verrors.errors
    )


@pytest.mark.asyncio
async def test_raidz2_below_minimum_disks_rejected():
    verrors = await _service()._validate_topology(_pool_data([_new_vdev('RAIDZ2', 3)]))
    assert [e.attribute for e in verrors.errors] == ['topology.data.0.disks']
    assert verrors.errors[0].errmsg == 'You need at least 4 disk(s) for this vdev type.'


@pytest.mark.asyncio
async def test_special_without_redundancy_rejected():
    verrors = await _service()._validate_topology(
        _pool_data([_new_vdev('RAIDZ2', 7)], special=[_new_vdev('STRIPE', 1)])
    )
    assert any(
        e.errmsg == 'A special vdev with no redundancy is not allowed when data vdevs are redundant.'
        for e in verrors.errors
    )


# ---------------------------------------------------------------------------
# force_topology bypasses the policy checks (but not structural ones)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_force_topology_bypasses_width_and_cap():
    verrors = await _service()._validate_topology(
        _pool_data([_new_vdev('RAIDZ2', 7), _new_vdev('RAIDZ2', 30)], force_topology=True)
    )
    assert verrors.errors == []


@pytest.mark.asyncio
async def test_force_topology_bypasses_special_redundancy():
    verrors = await _service()._validate_topology(
        _pool_data([_new_vdev('RAIDZ2', 7)], special=[_new_vdev('STRIPE', 1)], force_topology=True)
    )
    assert verrors.errors == []


@pytest.mark.asyncio
async def test_force_topology_does_not_bypass_minimum_disks():
    # Minimum disks is structural and still applies under force_topology.
    verrors = await _service()._validate_topology(
        _pool_data([_new_vdev('RAIDZ2', 3)], force_topology=True)
    )
    assert [e.attribute for e in verrors.errors] == ['topology.data.0.disks']
    assert verrors.errors[0].errmsg == 'You need at least 4 disk(s) for this vdev type.'


# ---------------------------------------------------------------------------
# force_topology is not permitted on Enterprise-licensed systems
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_force_topology_rejected_on_enterprise():
    verrors = await _service(is_enterprise=True)._validate_topology(
        _pool_data([_new_vdev('RAIDZ2', 7)], force_topology=True)
    )
    assert [e.attribute for e in verrors.errors] == ['force_topology']
    assert verrors.errors[0].errmsg == (
        'Bypassing pool topology validation is not supported on '
        'Enterprise-licensed systems.'
    )


@pytest.mark.asyncio
async def test_force_topology_not_checked_when_unset():
    # system.is_enterprise must not even be consulted when force_topology is off.
    service = _service(is_enterprise=True)
    verrors = await service._validate_topology(_pool_data([_new_vdev('RAIDZ2', 7)]))
    assert verrors.errors == []
    service.middleware['system.is_enterprise'].assert_not_called()
