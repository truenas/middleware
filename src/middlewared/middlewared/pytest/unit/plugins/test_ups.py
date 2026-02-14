import pytest

from unittest.mock import patch, mock_open

from middlewared.plugins.ups.utils import driver_choices, normalize_driver_string


ALL_TEST_DRIVERS = {'victronups', 'genericups', 'blazer_usb', 'tripplite_usb'}


@pytest.mark.parametrize('config_line,key,value', [
    (
        '"Victron/IMV"	"ups"	"1"	"(various)"	""	"victronups"',
        'victronups$(various)', 'Victron/IMV ups 1 (various) (victronups)'
    ),
    (
        '"Various"	"ups"	"1"	"(various)"	"Generic RUPS model"	"genericups upstype=4"',
        'genericups upstype=4$(various)', 'Various ups 1 (various) Generic RUPS model (genericups)'
    ),
    (
        '"Various"	"ups"	"1"	"(various)"	"Generic RUPS 2000 (Megatec M2501 cable)"	"genericups upstype=21"',
        'genericups upstype=21$(various)',
        'Various ups 1 (various) Generic RUPS 2000 (Megatec M2501 cable) (genericups)'
    ),
    (
        '"Victron/IMV"	"ups"	"1"	"Lite"	"crack cable"	"genericups upstype=10"',
        'genericups upstype=10$Lite', 'Victron/IMV ups 1 Lite crack cable (genericups)'
    ),
    (
        '"UNITEK"	"ups"	"2"	"Alpha 1200Sx"	"USB"	"blazer_usb"',
        'blazer_usb$Alpha 1200Sx', 'UNITEK ups 2 Alpha 1200Sx USB (blazer_usb)'
    ),
    (
        '"Tripp Lite"	"ups"	"2"	"SMART500RT1U"	"USB (older; product ID 0001, protocol 3005)"	"tripplite_usb"',
        'tripplite_usb$SMART500RT1U',
        'Tripp Lite ups 2 SMART500RT1U USB (older; product ID 0001, protocol 3005) (tripplite_usb)'
    ),
])
@patch('os.path.exists', lambda x: True)
def test__services_ups_service__driver_choices(config_line, key, value):
    driver_choices.cache_clear()
    with patch('middlewared.plugins.ups.utils.drivers_available', return_value=ALL_TEST_DRIVERS):
        with patch('builtins.open', mock_open(read_data=config_line)):
            assert driver_choices() == {key: value}


@pytest.mark.parametrize('driver_str,normalized', [
    ('victronups$(various)', 'driver = victronups'),
    ('genericups upstype=4$(various)', 'driver = genericups\n\tupstype=4'),
    ('genericups upstype=21$(various)', 'driver = genericups\n\tupstype=21'),
    ('genericups upstype=10$(various)', 'driver = genericups\n\tupstype=10'),
    ('blazer_usb$Alpha 1200Sx', 'driver = blazer_usb'),
    ('tripplite_usb$SMART500RT1U', 'driver = tripplite_usb'),
])
def test__services_ups_service__driver_string_normalization(driver_str, normalized):
    assert normalize_driver_string(driver_str) == normalized
