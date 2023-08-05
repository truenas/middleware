import pytest

from middlewared.plugins.enclosure_ import element_types


@pytest.mark.parametrize('data', [
    # Test each individual flag
    (0x100000, 'Identify on'),
    (0x080000, 'Fail on'),
    (0x000080, 'RQST mute'),
    (0x000040, 'Muted'),
    (0x000010, 'Remind'),
    (0x000008, 'INFO'),
    (0x000004, 'NON-CRIT'),
    (0x000002, 'CRIT'),
    (0x000001, 'UNRECOV'),
    # No flag
    (0x000000, None),
    # All flags
    (0x1800FF, 'Identify on, Fail on, RQST mute, Muted, Remind, INFO, NON-CRIT, CRIT, UNRECOV')
])
def test_alarm(data):
    value_raw, expected_result = data
    assert element_types.alarm(value_raw) == expected_result


@pytest.mark.parametrize('data', [
    # Test each individual flag
    (0x100000, 'Identify on'),
    (0x080000, 'Fail on'),
    (0x000001, 'Disabled'),
    # Test with no flags set
    (0x000000, None),
    # Test combinations
    (0x180000, 'Identify on, Fail on'),
    (0x100001, 'Identify on, Disabled'),
    (0x080001, 'Fail on, Disabled'),
    # Test with all flags set
    (0x180001, 'Identify on, Fail on, Disabled')
])
def test_comm(data):
    value_raw, expected_result = data
    assert element_types.comm(value_raw) == expected_result


@pytest.mark.parametrize('data', [
    # Test each individual flag
    (0x100010, '6.56A, Identify on'),
    (0x080020, '8.0A, Fail on'),
    (0x000830, '12.96A, Warn Over'),
    (0x000240, '5.76A, Crit Over'),
    # No flag
    (0x000000, '0.0A'),
    # Test with all flags set
    (0x1C0A10, '4.16A, Identify on, Fail on, Warn Over, Crit Over')
])
def test_current(data):
    value_raw, expected_result = data
    assert element_types.current(value_raw) == expected_result


@pytest.mark.parametrize('data', [
    # Test each individual flag
    (0x100000, 'Identify on'),
    (0x000200, 'Fail on'),
    (0x000100, 'Warn On'),
    # Test power cycle and power off time flags
    (0x000840, 'Power cycle 1min, power off for 16min'),
    # Test with no flags set
    (0x000000, None),
    # Test combinations
    (0x100200, 'Identify on, Fail on'),
    (0x100100, 'Identify on, Warn On'),
    (0x000300, 'Fail on, Warn On'),
    # Test with all flags set and power cycle time
    (0x100F4C, 'Identify on, Fail on, Warn On, Power cycle 15min, power off for 19min'),
])
def test_enclosure(data):
    value_raw, expected_result = data
    assert element_types.enclosure(value_raw) == expected_result


@pytest.mark.parametrize('data', [
    # Test each individual flag
    (0x100010, '6.56V, Identify on'),
    (0x080020, '8.0V, Fail on'),
    (0x000830, '12.96V, Warn over'),
    (0x000440, '17.44V, Warn under'),
    (0x000240, '5.76V, Crit over'),
    (0x000141, '3.21V, Crit under'),
    # Test with no flags set
    (0x000080, '1.28V'),
    # Test combinations
    (0x180010, '6.56V, Identify on, Fail on'),
    (0x1C0A10, '4.16V, Identify on, Fail on, Warn over, Warn under'),
    # Test with all flags set
    (0x1F0F1F, '7.83V, Identify on, Fail on, Warn over, Warn under, Crit over, Crit under'),
])
def test_volt(data):
    value_raw, expected_result = data
    assert element_types.volt(value_raw) == expected_result


@pytest.mark.parametrize('data', [
    (0x000000, '0 RPM'),
    (0x001000, '160 RPM'),
    (0x010000, '10240 RPM'),
    (0x7ff00, '524280 RPM'),
    # Ensure mask works correctly
    (0xFFFF00, '524280 RPM'),
    # Test with bits set outside the mask
    (0xABCDEF, '686080 RPM')
])
def test_cooling(data):
    value_raw, expected_result = data
    assert element_types.cooling(value_raw) == expected_result


@pytest.mark.parametrize('data', [
    (0x0000, None),
    # Check for minimum temperature
    (0x0100, '-19C'),
    # Check for an arbitrary temperature
    (0x8000, '108C'),
    # Check for maximum temperature
    (0xFF00, '235C'),
    # Check that extra bits do not affect the result
    (0xFFFF, '235C')
])
def test_temp(data):
    value_raw, expected_result = data
    assert element_types.temp(value_raw) == expected_result


@pytest.mark.parametrize('data', [
    # Test each individual flag
    (0x100000, 'Identify on'),
    (0x40, 'Fail on'),
    (0x800, 'DC overvoltage'),
    (0x400, 'DC undervoltage'),
    (0x200, 'DC overcurrent'),
    (0x8, 'Overtemp fail'),
    (0x4, 'Overtemp warn'),
    (0x2, 'AC fail'),
    (0x1, 'DC fail'),
    (0x10, 'Off'),
    # Test with no flags set
    (0x000000, None),
    # Test some combinations
    (0x100400, 'Identify on, DC undervoltage'),
    (0x40C, 'Fail on, DC overcurrent, Overtemp warn'),
    # Test with all flags set
    (
        0x10045F, '''Identify on, Fail on, DC overvoltage,
        DC undervoltage, DC overcurrent, Overtemp fail,
        Overtemp warn, AC fail, DC fail, Off'''
    )
])
def test_psu(data):
    value_raw, expected_result = data
    assert element_types.psu(value_raw) == expected_result


@pytest.mark.parametrize('data', [
    # Test each individual flag
    (0x200, 'Identify on'),
    (0x20, 'Fault on'),
    # Test with no flags set
    (0x0, None),
    # Test combinations
    (0x220, 'Identify on, Fault on')
])
def test_array_dev(data):
    value_raw, expected_result = data
    assert element_types.array_dev(value_raw) == expected_result


@pytest.mark.parametrize('data', [
    # Test each individual flag
    (0x000000, 'No information'),
    (0x010000, 'SAS 4x receptacle (SFF-8470) [max 4 phys]'),
    (0x020000, 'Mini SAS 4x receptacle (SFF-8088) [max 4 phys]'),
    (0x030000, 'QSFP+ receptacle (SFF-8436) [max 4 phys]'),
    (0x040000, 'Mini SAS 4x active receptacle (SFF-8088) [max 4 phys]'),
    (0x050000, 'Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]'),
    (0x060000, 'Mini SAS HD 8x receptacle (SFF-8644) [max 8 phys]'),
    (0x070000, 'Mini SAS HD 16x receptacle (SFF-8644) [max 16 phys]'),
    (0x080000, 'unknown external connector type: 0x8'),
    (0x090000, 'unknown external connector type: 0x9'),
    (0x0a0000, 'unknown external connector type: 0xa'),
    (0x0b0000, 'unknown external connector type: 0xb'),
    (0x0c0000, 'unknown external connector type: 0xc'),
    (0x0d0000, 'unknown external connector type: 0xd'),
    (0x0e0000, 'unknown external connector type: 0xe'),
    (0x0f0000, 'Vendor specific external connector'),
    (0x100000, 'SAS 4i plug (SFF-8484) [max 4 phys]'),
    (0x110000, 'Mini SAS 4i receptacle (SFF-8087) [max 4 phys]'),
    (0x120000, 'Mini SAS HD 4i receptacle (SFF-8643) [max 4 phys]'),
    (0x130000, 'Mini SAS HD 8i receptacle (SFF-8643) [max 8 phys]'),
    (0x140000, 'unknown internal wide connector type: 0x14'),
    (0x150000, 'unknown internal wide connector type: 0x15'),
    (0x160000, 'unknown internal wide connector type: 0x16'),
    (0x170000, 'unknown internal wide connector type: 0x17'),
    (0x180000, 'unknown internal wide connector type: 0x18'),
    (0x190000, 'unknown internal wide connector type: 0x19'),
    (0x200000, 'SAS Drive backplane receptacle (SFF-8482) [max 2 phys]'),
    (0x210000, 'SATA host plug [max 1 phy]'),
    (0x220000, 'SAS Drive plug (SFF-8482) [max 2 phys]'),
    (0x230000, 'SATA device plug [max 1 phy]'),
    (0x240000, 'Micro SAS receptacle [max 2 phys]'),
    (0x250000, 'Micro SATA device plug [max 1 phy]'),
    (0x260000, 'Micro SAS plug (SFF-8486) [max 2 phys]'),
    (0x270000, 'Micro SAS/SATA plug (SFF-8486) [max 2 phys]'),
    (0x280000, 'unknown internal connector to end device type: 0x28'),
    (0x290000, 'unknown internal connector to end device type: 0x29'),
    (0x2a0000, 'unknown internal connector to end device type: 0x2a'),
    (0x2b0000, 'unknown internal connector to end device type: 0x2b'),
    (0x2c0000, 'unknown internal connector to end device type: 0x2c'),
    (0x2d0000, 'unknown internal connector to end device type: 0x2d'),
    (0x2e0000, 'unknown internal connector to end device type: 0x2e'),
    (0x2f0000, 'SAS virtual connector [max 1 phy]'),
    (0x300000, 'reserved for internal connector type: 0x30'),
    (0x310000, 'reserved for internal connector type: 0x31'),
    (0x320000, 'reserved for internal connector type: 0x32'),
    (0x330000, 'reserved for internal connector type: 0x33'),
    (0x340000, 'reserved for internal connector type: 0x34'),
    (0x350000, 'reserved for internal connector type: 0x35'),
    (0x360000, 'reserved for internal connector type: 0x36'),
    (0x370000, 'reserved for internal connector type: 0x37'),
    (0x380000, 'reserved for internal connector type: 0x38'),
    (0x390000, 'reserved for internal connector type: 0x39'),
    (0x3a0000, 'reserved for internal connector type: 0x3a'),
    (0x3b0000, 'reserved for internal connector type: 0x3b'),
    (0x3c0000, 'reserved for internal connector type: 0x3c'),
    (0x3d0000, 'reserved for internal connector type: 0x3d'),
    (0x3e0000, 'reserved for internal connector type: 0x3e'),
    (0x3f0000, 'Vendor specific internal connector'),
    (0x400000, 'reserved connector type: 0x40'),
    (0x410000, 'reserved connector type: 0x41'),
    (0x420000, 'reserved connector type: 0x42'),
    (0x430000, 'reserved connector type: 0x43'),
    (0x440000, 'reserved connector type: 0x44'),
    (0x450000, 'reserved connector type: 0x45'),
    (0x460000, 'reserved connector type: 0x46'),
    (0x470000, 'reserved connector type: 0x47'),
    (0x480000, 'reserved connector type: 0x48'),
    (0x490000, 'reserved connector type: 0x49'),
    (0x4a0000, 'reserved connector type: 0x4a'),
    (0x4b0000, 'reserved connector type: 0x4b'),
    (0x4c0000, 'reserved connector type: 0x4c'),
    (0x4d0000, 'reserved connector type: 0x4d'),
    (0x4e0000, 'reserved connector type: 0x4e'),
    (0x4f0000, 'reserved connector type: 0x4f'),
    (0x500000, 'reserved connector type: 0x50'),
    (0x510000, 'reserved connector type: 0x51'),
    (0x520000, 'reserved connector type: 0x52'),
    (0x530000, 'reserved connector type: 0x53'),
    (0x540000, 'reserved connector type: 0x54'),
    (0x550000, 'reserved connector type: 0x55'),
    (0x560000, 'reserved connector type: 0x56'),
    (0x570000, 'reserved connector type: 0x57'),
    (0x580000, 'reserved connector type: 0x58'),
    (0x590000, 'reserved connector type: 0x59'),
    (0x5a0000, 'reserved connector type: 0x5a'),
    (0x5b0000, 'reserved connector type: 0x5b'),
    (0x5c0000, 'reserved connector type: 0x5c'),
    (0x5d0000, 'reserved connector type: 0x5d'),
    (0x5e0000, 'reserved connector type: 0x5e'),
    (0x5f0000, 'reserved connector type: 0x5f'),
    (0x600000, 'reserved connector type: 0x60'),
    (0x610000, 'reserved connector type: 0x61'),
    (0x620000, 'reserved connector type: 0x62'),
    (0x630000, 'reserved connector type: 0x63'),
    (0x640000, 'reserved connector type: 0x64'),
    (0x650000, 'reserved connector type: 0x65'),
    (0x660000, 'reserved connector type: 0x66'),
    (0x670000, 'reserved connector type: 0x67'),
    (0x680000, 'reserved connector type: 0x68'),
    (0x690000, 'reserved connector type: 0x69'),
    (0x6a0000, 'reserved connector type: 0x6a'),
    (0x6b0000, 'reserved connector type: 0x6b'),
    (0x6c0000, 'reserved connector type: 0x6c'),
    (0x6d0000, 'reserved connector type: 0x6d'),
    (0x6e0000, 'reserved connector type: 0x6e'),
    (0x6f0000, 'reserved connector type: 0x6f'),
    (0x700000, 'vendor specific connector type: 0x70'),
    (0x710000, 'vendor specific connector type: 0x71'),
    (0x720000, 'vendor specific connector type: 0x72'),
    (0x730000, 'vendor specific connector type: 0x73'),
    (0x740000, 'vendor specific connector type: 0x74'),
    (0x750000, 'vendor specific connector type: 0x75'),
    (0x760000, 'vendor specific connector type: 0x76'),
    (0x770000, 'vendor specific connector type: 0x77'),
    (0x780000, 'vendor specific connector type: 0x78'),
    (0x790000, 'vendor specific connector type: 0x79'),
    (0x7a0000, 'vendor specific connector type: 0x7a'),
    (0x7b0000, 'vendor specific connector type: 0x7b'),
    (0x7c0000, 'vendor specific connector type: 0x7c'),
    (0x7d0000, 'vendor specific connector type: 0x7d'),
    (0x7e0000, 'vendor specific connector type: 0x7e'),
    (0x7f0000, 'vendor specific connector type: 0x7f'),
    # Test out of bounds connector type
    (0x800000, 'unexpected connector type: 0x80'),
    # Test connector type with fail on
    (0x220040, 'SAS Drive plug (SFF-8482) [max 2 phys], Fail On'),
    # Test out of bounds connector type with fail on
    (0x800040, 'unexpected connector type: 0x80, Fail On')
])
def test_sas_conn(data):
    value_raw, expected_result = data
    assert element_types.sas_conn(value_raw) == expected_result


@pytest.mark.parametrize('data', [
    (0x0000, None),
    (0x800000, 'Identify on'),
    (0x400000, 'Fail on'),
    (0xC00000, 'Identify on, Fail on')
])
def test_sas_exp(data):
    value_raw, expected_result = data
    assert element_types.sas_exp(value_raw) == expected_result
