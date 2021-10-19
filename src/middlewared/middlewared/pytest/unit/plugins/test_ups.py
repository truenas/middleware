import pytest
import textwrap

from mock import Mock, patch, mock_open

from middlewared.plugins.ups import UPSService


@pytest.mark.parametrize('expected', [
    'victronups$(various)',
    'genericups upstype=4$(various)',
    'genericups upstype=21$(various)',
    'genericups upstype=10$Lite',
    'blazer_usb$Alpha 1200Sx',
    'tripplite_usb$SMART500RT1U',
])
@patch('builtins.open', mock_open(read_data=textwrap.dedent('''\
    # Network UPS Tools - 2.7.4 - Hardware Compatibility List
    # version=2
    #
    # This file is used for various purposes, like building the HTML compatibility
    # list or displaying information in NUT configuration tools.
    #
    # If you write a new driver, modify an existing one to add more support,
    # or just know about some equipment that isn't listed but should be,
    # please send us a patch to update this file.
    #
    "Ablerex"	"ups"	"2"	"MS-RT"	""	"blazer_ser"
    "Ablerex"	"ups"	"2"	"625L"	"USB"	"blazer_usb"
    "Ablerex"	"ups"	"2"	"Hope Office 400/600"	""	"blazer_ser"
    
    "ActivePower"	"ups"	"2"	"400VA"	""	"blazer_ser"
    "ActivePower"	"ups"	"2"	"1400VA"	""	"blazer_ser"
    "ActivePower"	"ups"	"2"	"2000VA"	""	"blazer_ser"
    
    "Advice"	"ups"	"2"	"TopGuard 2000"	""	"blazer_ser"
    "Victron/IMV"	"ups"	"1"	"(various)"	""	"victronups"
    "Various"	"ups"	"1"	"(various)"	"Generic RUPS model"	"genericups upstype=4"
    
    "AEC"	"ups"	"1"	"MiniGuard UPS 700"	"Megatec M2501 cable"	"genericups upstype=21"
    "Various"	"ups"	"1"	"(various)"	"Generic RUPS 2000 (Megatec M2501 cable)"	"genericups upstype=21"
    
    "Victron/IMV"	"ups"	"1"	"(various)"	""	"victronups"
    "Victron/IMV"	"ups"	"1"	"Lite"	"crack cable"	"genericups upstype=10"
    
    "UNITEK"	"ups"	"2"	"Alpha 1200Sx"	"USB"	"blazer_usb"
    
    "Tripp Lite"	"ups"	"2"	"SMART500RT1U"	"USB (older; product ID 0001, protocol 3005)"	"tripplite_usb"
    "Tripp Lite"	"ups"	"3"	"SMART500RT1U"	"USB (newer; protocol/product ID 3005)"	"usbhid-ups"'''
                                                            '''	# http://www.tripplite.com/en/products/model.cfm
''')))
@patch('os.path.exists', lambda x: True)
def test__services_ups_service__driver_choices(expected):
    svc = UPSService(Mock())
    assert expected in svc.driver_choices()
