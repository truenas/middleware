import pytest

from middlewared.plugins.enclosure_ import identification


@pytest.mark.parametrize('data', [
    # M series
    ('ECStream_4024Sp', 'TRUENAS-M40', ('M40', True)),
    ('ECStream_4024Ss', 'TRUENAS-M40', ('M40', True)),
    ('iX_4024Sp', 'TRUENAS-M40', ('M40', True)),
    ('iX_4024Ss', 'TRUENAS-M40', ('M40', True)),
    # X series
    ('CELESTIC_P3215-O', 'TRUENAS-X20', ('X20', True)),
    ('CELESTIC_P3217-B', 'TRUENAS-X20', ('X20', True)),
    # H series
    ('BROADCOM_VirtualSES', 'TRUENAS-H10', ('H10', True)),
    ('BROADCOM_VirtualSES', 'NOT_LEGIT', ('', False)),
    # R series (just uses dmi info for model)
    ('ECStream_FS1', 'TRUENAS-R10', ('R10', True)),
    ('ECStream_FS2', 'TRUENAS-R20', ('R20', True)),
    ('ECStream_DSS212Sp', 'TRUENAS-R50', ('R50', True)),
    ('ECStream_DSS212Ss', 'TRUENAS-R40', ('R40', True)),
    ('iX_FS1L', 'TRUENAS-R10', ('R10', True)),
    ('iX_FS2', 'TRUENAS-R10', ('R10', True)),
    ('iX_DSS212Sp', 'TRUENAS-R10', ('R10', True)),
    ('iX_DSS212Ss', 'TRUENAS-R10', ('R10', True)),
    # R20
    ('iX_TrueNASR20p', 'TRUENAS-R20', ('R20', True)),
    ('iX_2012Sp', 'TRUENAS-R20A', ('R20A', True)),
    ('iX_TrueNASSMCSC826-P', 'TRUENAS-R20B', ('R20B', True)),
    # R20 variants (and minis)
    ('AHCI_SGPIOEnclosure', 'TRUENAS-R20', ('R20', True)),
    ('AHCI_SGPIOEnclosure', 'TRUENAS-R20A', ('R20A', True)),
    ('AHCI_SGPIOEnclosure', 'TRUENAS-R20B', ('R20B', True)),
    ('AHCI_SGPIOEnclosure', 'TRUENAS-MINI-R', ('MINI-R', True)),
    ('AHCI_SGPIOEnclosure', 'FREENAS-MINI-X', ('MINI-X', True)),
    ('AHCI_SGPIOEnclosure', 'OOPS', ('', False)),
    # R50
    ('iX_eDrawer4048S1', 'TRUENAS-R50', ('R50', True)),
    ('iX_eDrawer4048S2', 'TRUENAS-R50', ('R50', True)),
    # JBODS
    ('ECStream_3U16RJ-AC.r3', 'TRUENAS-F60', ('E16', False)),
    ('Storage_1729', 'TRUENAS-F60', ('E24', False)),
    ('QUANTA_JB9SIM', 'TRUENAS-F60', ('E60', False)),
    ('CELESTIC_X2012', 'TRUENAS-F60', ('ES12', False)),
    ('ECStream_4024J', 'TRUENAS-F60', ('ES24', False)),
    ('iX_4024J', 'TRUENAS-F60', ('ES24', False)),
    ('ECStream_2024Jp', 'TRUENAS-F60', ('ES24F', False)),
    ('ECStream_2024Js', 'TRUENAS-F60', ('ES24F', False)),
    ('iX_2024Jp', 'TRUENAS-F60', ('ES24F', False)),
    ('iX_2024Js', 'TRUENAS-F60', ('ES24F', False)),
    ('CELESTIC_R0904-F0001-01', 'TRUENAS-F60', ('ES60', False)),
    ('HGST_H4060-J', 'TRUENAS-M60', ('ES60G2', False)),
    ('HGST_H4102-J', 'TRUENAS-F60', ('ES102', False)),
    ('VikingES_NDS-41022-BB', 'TRUENAS-M30', ('ES102G2', False)),
])
def test_get_enclosure_model_and_controller(data):
    key, dmi, expected_result = data
    assert identification.get_enclosure_model_and_controller(key, dmi) == expected_result
