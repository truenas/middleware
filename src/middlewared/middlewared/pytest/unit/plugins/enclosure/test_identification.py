import pytest

from middlewared.plugins.enclosure_ import identification


@pytest.mark.parametrize('data', [
    # M series
    ('ECStream_4024Sp', 'TRUENAS-M40', ('M Series', True)),
    ('ECStream_4024Ss', 'TRUENAS-M40', ('M Series', True)),
    ('iX_4024Sp', 'TRUENAS-M40', ('M Series', True)),
    ('iX_4024Ss', 'TRUENAS-M40', ('M Series', True)),
    # X series
    ('CELESTIC_P3215-O', 'TRUENAS-X20', ('X Series', True)),
    ('CELESTIC_P3217-B', 'TRUENAS-X20', ('X Series', True)),
    # R series (just uses dmi info for model)
    ('ECStream_FS1', 'TRUENAS-R10', ('R10', True)),
    ('ECStream_FS2', 'TRUENAS-R20', ('R20', True)),
    ('ECStream_DSS212Sp', 'TRUENAS-R50', ('R50', True)),
    ('ECStream_DSS212Ss', 'TRUENAS-R40', ('R40', True)),
    ('iX_FS1', 'TRUENAS-R10', ('R10', True)),
    ('iX_FS2', 'TRUENAS-R10', ('R10', True)),
    ('iX_DSS212Sp', 'TRUENAS-R10', ('R10', True)),
    ('iX_DSS212Ss', 'TRUENAS-R10', ('R10', True)),
    # R20
    ('iX_TrueNAS R20p', 'TRUENAS-R20', ('R20', True)),
    ('iX_TrueNAS 2012Sp', 'TRUENAS-R20', ('R20', True)),
    ('iX_TrueNAS SMC SC826-P', 'TRUENAS-R20', ('R20', True)),
    # R20 variants (and minis)
    ('AHCI_SGPIOEnclosure', 'TRUENAS-R20', ('R20', True)),
    ('AHCI_SGPIOEnclosure', 'TRUENAS-R20A', ('R20A', True)),
    ('AHCI_SGPIOEnclosure', 'TRUENAS-R20B', ('R20B', True)),
    ('AHCI_SGPIOEnclosure', 'TRUENAS-MINI-R', ('TRUENAS-MINI-R', True)),
    ('AHCI_SGPIOEnclosure', 'FREENAS-MINI-X', ('FREENAS-MINI-X', True)),
    ('AHCI_SGPIOEnclosure', 'OOPS', ('', False)),
    # R50
    ('iX_eDrawer4048S1', 'TRUENAS-R50', ('R50', True)),
    ('iX_eDrawer4048S2', 'TRUENAS-R50', ('R50', True)),
    # JBODS
    ('ECStream_3U16RJ-AC.r3', 'TRUENAS-F60', ('E16', False)),
    ('Storage_1729', 'TRUENAS-F60', ('E24', False)),
    ('QUANTA _JB9 SIM', 'TRUENAS-F60', ('E60', False)),
    ('CELESTIC_X2012', 'TRUENAS-F60', ('ES12', False)),
    ('ECStream_4024J', 'TRUENAS-F60', ('ES24', False)),
    ('iX_4024J', 'TRUENAS-F60', ('ES24', False)),
    ('ECStream_2024Jp', 'TRUENAS-F60', ('ES24F', False)),
    ('ECStream_2024Js', 'TRUENAS-F60', ('ES24F', False)),
    ('iX_2024Jp', 'TRUENAS-F60', ('ES24F', False)),
    ('iX_2024Js', 'TRUENAS-F60', ('ES24F', False)),
    ('CELESTIC_R0904', 'TRUENAS-F60', ('ES60', False)),
    ('HGST_H4102-J', 'TRUENAS-F60', ('ES102', False)),
    ('VikingES_NDS-41022-BB', 'TRUENAS-F60', ('ES102S', False))
])
def test_get_enclosure_model_and_controller(data):
    key, dmi, expected_result = data
    assert identification.get_enclosure_model_and_controller(key, dmi) == expected_result
